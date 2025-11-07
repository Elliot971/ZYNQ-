import torch
import torch.nn as nn
from config import SimulationConfig


def _complex_from_ri(x: torch.Tensor) -> torch.Tensor:
    """
    x: (..., 2) with [..., 0]=Re, [..., 1]=Im  -> complex tensor (...,)
    """
    assert x.shape[-1] == 2, f"Last dim must be 2 (RI), got {x.shape}"
    return torch.view_as_complex(x.to(torch.float32))

def _ri_from_complex(c: torch.Tensor) -> torch.Tensor:
    return torch.view_as_real(c.to(torch.complex64))

def _svd_condition(H: torch.Tensor, eps: float = 1e-9) -> torch.Tensor:
    """
    Rough condition number of H via singular values of H^H H.
    H: (B,R,T) complex -> cond: (B,)
    """
    HhH = H.conj().transpose(-1, -2) @ H                      # (B,T,T)
    s = torch.linalg.svdvals(HhH).clamp_min(eps)              # (B,T)
    return (s.max(dim=-1).values / s.min(dim=-1).values)      # (B,)

def _tikhonov_ls_batch(H: torch.Tensor, y: torch.Tensor, lam_b: torch.Tensor) -> torch.Tensor:
    """
    Batch-wise Tikhonov LS: solve x = argmin ||H x - y||^2 + lam * ||x||^2
    H: (B,R,T) complex, y: (B,R) complex, lam_b: (B,) real
    returns x: (B,T) real
    """
    B, R, T = H.shape
    Hh = H.conj().transpose(-1, -2)                           # (B,T,R)
    A = Hh @ H  # (B,T,T)
    I = torch.eye(T, device=H.device, dtype=H.dtype).expand(B, T, T)
    # 向量 λ → 对角阵
    Lambda = torch.diag_embed(lam_b.to(H.dtype))  # (B,T,T)
    A = A + Lambda
    b = Hh @ y.unsqueeze(-1)                                   # (B,T,1)
    x = torch.linalg.solve(A, b).squeeze(-1)                   # (B,T) complex
    return x.real.to(torch.float32)

def _adaptive_lambda(H: torch.Tensor,
                     base: float = 1e-3,
                     kmin: float = 1.0,
                     kmax: float = 1e4) -> torch.Tensor:
    """
    Adaptive lambda based on condition number of H.
    Returns lam per-sample: (B,)
    """
    cond = _svd_condition(H)                                   # (B,)
    cond_clamped = cond.clamp(kmin, kmax)
    scale = cond_clamped / kmin                                # >=1
    return torch.as_tensor(base, device=H.device, dtype=torch.float32) * scale

def _tikhonov_ls(H: torch.Tensor, y: torch.Tensor, lam: float = 1e-3) -> torch.Tensor:
    """
    Solve x = argmin ||H x - y||^2 + lam ||x||^2
    H: (B, R, T) complex, y: (B, R) complex  ->  x: (B, T) real (clipped >=0)
    """
    B, R, T = H.shape
    Hh = H.conj().transpose(-1, -2)           # (B, T, R)
    A = Hh @ H                                 # (B, T, T)
    I = torch.eye(T, device=H.device, dtype=H.dtype).expand(B, T, T)
    A = A + lam * I
    b = Hh @ y.unsqueeze(-1)                   # (B, T, 1)
    x = torch.linalg.solve(A, b).squeeze(-1)   # (B, T) complex
    return x.real.to(torch.float32)

class MatrixMLP(nn.Module):
    """
    新方案模型：输入 (B, 5, 4) 的幅度矩阵，输出 4 维 x。
    - 前4行是导频幅度 -> 估计 H_amp (Nr x Nt)
    - 第5行为数据幅度 -> y_data_amp
    - 先用伪逆给出 x_LS 基线，再用小型 MLP 进行残差修正
    """
    def __init__(self, config: SimulationConfig):
        super().__init__()
        self.config = config
        in_dim = 5 * config.NUM_RX_ANTENNAS  # 5*4=20
        self.net = nn.Sequential(
            nn.Linear(in_dim + config.NUM_TAGS, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, config.NUM_TAGS)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 5, 4)
        B = x.shape[0]
        # 构造 H_amp 与 y_data_amp
        H_amp = x[:, 0:4, :].permute(0, 2, 1).contiguous()  # (B, Nr=4, Nt=4)
        y_data = x[:, 4, :].unsqueeze(-1)                  # (B, Nr=4, 1)

        # 线性基线解 x_LS = pinv(H) @ y
        H_pinv = torch.linalg.pinv(H_amp)                  # (B, Nt=4, Nr=4)
        x_ls = torch.matmul(H_pinv, y_data).squeeze(-1)    # (B, Nt=4)
        x_ls = torch.nan_to_num(x_ls, nan=0.0, posinf=1.0, neginf=0.0)
        x_ls = torch.clamp(x_ls, 0.0, 1.0)

        # MLP 残差修正
        flat = x.view(B, -1)
        mlp_in = torch.cat([flat, x_ls], dim=-1)
        delta = self.net(mlp_in)
        x_pred = torch.clamp(x_ls + delta, 0.0, 1.0)
        return x_pred

# class StructuredSolver(nn.Module):
#     """
#     I/Q coherent structured solver (drop-in replacement; class name unchanged).

#     Input:
#       x: (B, 5, 2, NUM_RX_ANTENNAS, W)  # 4 pilot slots + 1 data slot, I/Q, R antennas, W samples

#     Pipeline:
#       - Coherent average over time -> Y (B,5,R) complex
#       - Pilot slots directly form H (B,R,T=4)
#       - Scale normalization by pilot power (stabilizes training/inference)
#       - Adaptive Tikhonov-LS to get x_ls (non-negative real)
#       - Optional ΔH residual head -> re-solve x (x_tilde)
#       - Small refinement head around LS/tuned solution -> x_hat (non-negative)
#       - Output: concat [x_hat, |H|.reshape(B, R*T)]  -> shape (B, 4+16)
#     """
#     def __init__(self, config: SimulationConfig):
#         super(StructuredSolver, self).__init__()
#         self.config = config
#         self.num_tags = config.NUM_TAGS            # 4
#         self.num_rx   = config.NUM_RX_ANTENNAS     # 4

#         # options
#         self.base_lambda = float(getattr(config, "TIKHONOV_LAMBDA", 1e-3))
#         self.enable_adaptive_lambda = bool(getattr(config, "ADAPTIVE_LAMBDA", True))
#         self.enable_delta_h = bool(getattr(config, "ENABLE_DELTA_H", False))
#         self.use_sigmoid_out = bool(getattr(config, "X_IN_UNIT_INTERVAL", True))  # else Softplus

#         # ΔH head (optional): predict residual complex delta-H from [H_re,H_im,y_re,y_im]
#         if self.enable_delta_h:
#             dh_in = (self.num_rx * self.num_tags * 2) + (self.num_rx * 2)  # [vec(H_re,H_im), y_re,y_im]
#             dh_out = self.num_rx * self.num_tags * 2                       # real+imag for each H entry
#             self.delta_h_head = nn.Sequential(
#                 nn.Linear(dh_in, 192), nn.GELU(), nn.LayerNorm(192),
#                 nn.Linear(192, 192),   nn.GELU(), nn.LayerNorm(192),
#                 nn.Linear(192, dh_out)
#             )

#         # refinement head around LS / ΔH-LS, with diagnostics (cond, |y|_2)
#         # feats = [vec(H_re,H_im), y_re, y_im, x_ls, (optional x_tilde), cond, ynorm]
#         extra_dims = 2  # [cond, ynorm]
#         d_in = (self.num_rx*self.num_tags*2) + (self.num_rx*2) + self.num_tags + extra_dims
#         if self.enable_delta_h:
#             d_in += self.num_tags  # include x_tilde
#         self.refine = nn.Sequential(
#             nn.Linear(d_in, 192), nn.GELU(), nn.LayerNorm(192),
#             nn.Linear(192, 192), nn.GELU(), nn.LayerNorm(192),
#             nn.Linear(192, self.num_tags)
#         )
#         self.softplus = nn.Softplus()
#         self.sigmoid  = nn.Sigmoid()

#     @staticmethod
#     def _coherent_mean_over_time(X_ri: torch.Tensor) -> torch.Tensor:
#         """
#         Coherent average along time axis.
#         X_ri: (B,F,2,R,W) -> complex (B,F,R)
#         """
#         X_ri_perm = X_ri.permute(0, 1, 3, 4, 2).contiguous()   # (B,F,R,W,2)
#         Xc = _complex_from_ri(X_ri_perm)                       # (B,F,R,W) complex
#         return Xc.mean(dim=-1)                                 # (B,F,R)

#     @staticmethod
#     def _pilot_scale_norm(Yc: torch.Tensor) -> torch.Tensor:
#         """
#         Normalize by pilot average power to remove global gain ambiguity.
#         Yc: (B,5,R) complex -> normalized (B,5,R) complex
#         """
#         pilot_power = Yc[:, 0:4, :].abs().pow(2).mean(dim=(1, 2), keepdim=True)  # (B,1,1)
#         scale = pilot_power.sqrt().clamp_min(1e-8)
#         return Yc / scale

#     def forward(self, x: torch.Tensor) -> torch.Tensor:
#         """
#         x: (B, 5, 2, NUM_RX_ANTENNAS, W)
#         返回：
#           final_prediction: (B, 4+16) = [x_hat(4), |H|展平(16)]
#         """
#         B = x.shape[0]

#         # 1) coherent average -> complex slot-level observations
#         Y = self._coherent_mean_over_time(x)                   # (B,5,R) complex

#         # 2) pilot-based scale normalization (stabilizes training/inference)
#         Y = self._pilot_scale_norm(Y)                          # (B,5,R)

#         # 3) build H from pilot slots (columns), get data y
#         Hp = Y[:, 0:self.num_tags, :]                          # (B,T=4,R)
#         H = torch.stack([Hp[:, t, :] for t in range(self.num_tags)], dim=-1)  # (B,R,T)
#         y_data = Y[:, self.num_tags, :]                        # (B,R)

#         # diagnostics
#         condH = _svd_condition(H).unsqueeze(-1)                # (B,1)
#         y_norm = y_data.abs().norm(dim=-1, keepdim=True)       # (B,1)

#         # 4) adaptive lambda (per-sample)
#         lam_b = _adaptive_lambda(H, base=self.base_lambda) if self.enable_adaptive_lambda \
#                 else torch.full((B,), float(self.base_lambda), device=x.device)

#         # 5) Tikhonov-LS baseline
#         x_ls = _tikhonov_ls_batch(H, y_data, lam_b)            # (B,T) real>=0

#         # 6) optional ΔH residual + re-solve
#         x_tilde = None
#         if self.enable_delta_h:
#             H_re = H.real.reshape(B, -1)
#             H_im = H.imag.reshape(B, -1)
#             y_re = y_data.real.reshape(B, -1)
#             y_im = y_data.imag.reshape(B, -1)
#             dh_in = torch.cat([H_re, H_im, y_re, y_im], dim=-1)             # (B, 2RT + 2R)
#             dh_vec = self.delta_h_head(dh_in)                                # (B, 2RT)
#             dH_re, dH_im = torch.chunk(dh_vec, 2, dim=-1)
#             dH = torch.complex(dH_re.reshape(B, self.num_rx, self.num_tags),
#                                dH_im.reshape(B, self.num_rx, self.num_tags)) # (B,R,T)
#             H_tilde = H + dH
#             lam_b2 = _adaptive_lambda(H_tilde, base=self.base_lambda) if self.enable_adaptive_lambda \
#                      else lam_b
#             x_tilde = _tikhonov_ls_batch(H_tilde, y_data, lam_b2)           # (B,T)

#         # 7) refinement around LS (and x_tilde if exists)
#         H_re = H.real.reshape(B, -1)
#         H_im = H.imag.reshape(B, -1)
#         y_re = y_data.real.reshape(B, -1)
#         y_im = y_data.imag.reshape(B, -1)

#         feats = [H_re, H_im, y_re, y_im, x_ls, condH, y_norm]
#         if x_tilde is not None:
#             feats.append(x_tilde)
#         feats = torch.cat(feats, dim=-1)

#         dx = self.refine(feats)                                               # (B,T)
#         x_base = x_tilde if x_tilde is not None else x_ls
#         x_hat = x_base + dx
#         x_hat = self.sigmoid(x_hat) if self.use_sigmoid_out else self.softplus(x_hat)

#         # 8) output concat: x_hat + |H| (for backward compatibility with your label format)
#         H_abs_flat = H.abs().reshape(B, -1)                                   # (B, R*T) = (B,16)
#         final_prediction = torch.cat([x_hat, H_abs_flat], dim=1)              # (B, 4+16)

#         return final_prediction


class ResidualMLP(nn.Module):
    """恒维度的前馈残差块：dim -> hidden -> dim，保持输入/输出同维度"""
    def __init__(self, dim: int, hidden: int, p: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(dim, hidden)
        self.fc2 = nn.Linear(hidden, dim)
        self.act = nn.GELU()
        self.do = nn.Dropout(p)

    def forward(self, x):
        y = self.fc1(x)
        y = self.act(y)
        y = self.do(y)
        y = self.fc2(y)
        y = self.do(y)
        return self.act(x + y)


class StructuredSolver(nn.Module):
    """
    Structured, SNR-aware solver with:
      - Per-antenna pilot normalization (PAN)
      - Noise/SNR estimation from raw I/Q
      - Adaptive Tikhonov (LambdaNet)
      - Delta-H residual head (enabled by default)
      - Gated fusion of x_ls and x_tilde
      - Deep residual refinement (stem to hid, then fixed-dim residual blocks)
      - Configurable output activation (default: linear, no clamp)
    """
    def __init__(self, config: SimulationConfig):
        super().__init__()
        self.config = config
        self.num_tags = config.NUM_TAGS            # 4
        self.num_rx   = config.NUM_RX_ANTENNAS     # 4
        self.W        = getattr(config, "SAMPLES_PER_SLOT", None)

        # --------------- Options ---------------
        self.base_lambda = float(getattr(config, "TIKHONOV_LAMBDA", 1e-3))
        self.enable_adaptive_lambda = True
        self.enable_delta_h = True
        self.use_softplus_out = bool(getattr(config, "X_USE_SOFTPLUS_OUT", False))
        self.output_clip_bounds = getattr(config, "X_OUTPUT_CLIP_BOUNDS", None)
        self.dropout_p = 0.1

        hid = 256
        dh_hid = 384

        # --------------- LambdaNet (自适应λ) ---------------
        self.lambda_net = nn.Sequential(
            nn.Linear(3, hid), nn.GELU(),
            nn.Linear(hid, hid), nn.GELU(),
            nn.Linear(hid, self.num_tags)
        )
        self.softplus = nn.Softplus()

        # --------------- ΔH Head ---------------
        if self.enable_delta_h:
            d_in_dh = (self.num_rx * self.num_tags * 2) + (self.num_rx * 2)  # [H_re,H_im,y_re,y_im]
            d_out_dh = self.num_rx * self.num_tags * 2
            self.delta_h_head = nn.Sequential(
                nn.Linear(d_in_dh, dh_hid), nn.GELU(),
                nn.Dropout(self.dropout_p),
                nn.Linear(dh_hid, dh_hid), nn.GELU(),
                nn.Dropout(self.dropout_p),
                nn.Linear(dh_hid, d_out_dh)
            )

        # --------------- Gate: 融合 x_ls 与 x_tilde ---------------
        self.gate_mlp = nn.Sequential(
            nn.Linear(3, hid), nn.GELU(),
            nn.Linear(hid, 1),
            nn.Sigmoid()
        )

        # --------------- Refinement (修正维度问题的版本) ---------------
        # feats 维度：2*R*T + 2*R + T + 3 = 47
        d_in_refine = (self.num_rx*self.num_tags*2) + (self.num_rx*2) + self.num_tags + 3  # = 47
        self.refine_stem = nn.Sequential(
            nn.Linear(d_in_refine, hid),
            nn.GELU(),
            nn.Dropout(self.dropout_p)
        )
        # 若干恒维度的残差块（输入输出都是 hid）
        self.refine_blocks = nn.Sequential(
            ResidualMLP(hid, hidden=hid, p=self.dropout_p),
            ResidualMLP(hid, hidden=hid, p=self.dropout_p),
            ResidualMLP(hid, hidden=hid, p=self.dropout_p),
        )
        self.refine_head = nn.Linear(hid, self.num_tags)

    # ---------- 内部函数：与之前一致 ----------
    @staticmethod
    def _coherent_mean_over_time(X_ri: torch.Tensor) -> torch.Tensor:
        X_ri_perm = X_ri.permute(0, 1, 3, 4, 2).contiguous()   # (B,F,R,W,2)
        Xc = _complex_from_ri(X_ri_perm)                       # (B,F,R,W)
        return Xc.mean(dim=-1)                                 # (B,F,R)

    @staticmethod
    def _per_antenna_norm(Yc: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
        pilot = Yc[:, :4, :]                                   # (B,4,R)
        pw = pilot.abs().pow(2).mean(dim=1, keepdim=True)      # (B,1,R)
        scale = pw.sqrt().clamp_min(eps)                       # (B,1,R)
        return Yc / scale

    @staticmethod
    def _estimate_noise_power(X_ri: torch.Tensor, eps: float = 1e-12) -> torch.Tensor:
        B, F, _, R, W = X_ri.shape
        Xc = _complex_from_ri(X_ri.permute(0,1,3,4,2).contiguous())  # (B,F,R,W)
        Xm = Xc.mean(dim=-1, keepdim=True)                    # (B,F,R,1)
        resid = Xc - Xm                                       # (B,F,R,W)
        var = (resid.abs().pow(2).mean(dim=-1)).mean(dim=(1,2))  # (B,)
        return var.view(B,1).clamp_min(eps)

    def _build_H_y(self, Y: torch.Tensor):
        B = Y.size(0); T = self.num_tags
        Hp = Y[:, :T, :]                                      # (B,T,R)
        H = torch.stack([Hp[:, t, :] for t in range(T)], dim=-1)  # (B,R,T)
        y = Y[:, T, :]                                        # (B,R)
        return H, y

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B = x.shape[0]

        # 1) 相干平均
        Y = self._coherent_mean_over_time(x)                  # (B,5,R) complex

        # 2) PAN 逐天线归一化
        Y = self._per_antenna_norm(Y)                         # (B,5,R)

        # 3) 估计噪声 -> log_snr
        sigma2_est = self._estimate_noise_power(x)            # (B,1)
        pilot_pw = Y[:, :self.num_tags, :].abs().pow(2).mean(dim=(1,2), keepdim=False)  # (B,)
        log_snr = torch.log( (pilot_pw.view(B,1) / (sigma2_est + 1e-12)) + 1e-12 )      # (B,1)

        # 4) 构建 H, y 和诊断量
        H, y_data = self._build_H_y(Y)                        # H:(B,R,T), y:(B,R)
        condH = _svd_condition(H).unsqueeze(-1)               # (B,1)
        y_norm = y_data.abs().norm(dim=-1, keepdim=True)      # (B,1)

        # 5) LambdaNet
        if self.enable_adaptive_lambda:
            lam_in = torch.cat([torch.log(condH + 1e-8), y_norm, log_snr], dim=-1)  # (B,3)
            lam_b = self.softplus(self.lambda_net(lam_in)) + 1e-6       # (B,)
            lam_b = lam_b * self.base_lambda
        else:
            lam_b = torch.full((B,), float(self.base_lambda), device=x.device)

        # 6) 基线解
        x_ls = _tikhonov_ls_batch(H, y_data, lam_b)           # (B,T)

        # 7) ΔH + 再解
        x_tilde = None
        if self.enable_delta_h:
            H_re = H.real.reshape(B, -1); H_im = H.imag.reshape(B, -1)
            y_re = y_data.real.reshape(B, -1); y_im = y_data.imag.reshape(B, -1)
            dh_in = torch.cat([H_re, H_im, y_re, y_im], dim=-1)           # (B, 2RT + 2R)
            dh_vec = self.delta_h_head(dh_in)                             # (B, 2RT)
            dH_re, dH_im = torch.chunk(dh_vec, 2, dim=-1)
            dH = torch.complex(dH_re.reshape(B, self.num_rx, self.num_tags),
                               dH_im.reshape(B, self.num_rx, self.num_tags))  # (B,R,T)
            H_tilde = H + dH
            x_tilde = _tikhonov_ls_batch(H_tilde, y_data, lam_b)          # (B,T)

        # 8) 门控融合
        if x_tilde is not None:
            gate_in = torch.cat([torch.log(condH + 1e-8), y_norm, log_snr], dim=-1)  # (B,3)
            gate = self.gate_mlp(gate_in)                                            # (B,1)
            x_base = (1.0 - gate) * x_ls + gate * x_tilde                            # (B,T)
        else:
            x_base = x_ls

        # 9) 精炼
        H_re = H.real.reshape(B, -1); H_im = H.imag.reshape(B, -1)
        y_re = y_data.real.reshape(B, -1); y_im = y_data.imag.reshape(B, -1)
        feats = torch.cat([H_re, H_im, y_re, y_im, x_base,
                           torch.log(condH + 1e-8), y_norm, log_snr], dim=-1)  # (B,47)
        h = self.refine_stem(feats)                   # (B, hid)
        h = self.refine_blocks(h)                     # (B, hid)
        dx = self.refine_head(h)                      # (B, T)

        x_hat = x_base + dx
        # if getattr(self.config, "X_ENFORCE_REAL_INTERVAL", True):
        #     low, high = getattr(self.config, "X_INTERVAL_BOUNDS", (-1.0, 1.0))
        #     x_hat = torch.clamp(x_hat, low, high)
        if self.use_softplus_out:
            x_hat = self.softplus(x_hat)
        if self.output_clip_bounds is not None:
            low, high = self.output_clip_bounds
            x_hat = torch.clamp(x_hat, low, high)

        # 10) 输出
        H_abs_flat = H.abs().reshape(B, -1)           # (B,16)
        final_prediction = torch.cat([x_hat, H_abs_flat], dim=1)
        self.last_lambda = lam_b.detach().cpu().numpy()  # 用于分析
        return final_prediction
