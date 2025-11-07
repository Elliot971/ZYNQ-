"""
算法推理模块

功能:
- 加载训练好的PyTorch模型
- 执行温度估计推理
- 反射系数转温度计算

作者: AI Assistant
日期: 2025-11-05
"""

import numpy as np
import torch
import torch.nn as nn
from typing import Dict, Tuple
from pathlib import Path

# 导入模型定义
from model import StructuredSolver
from config import SimulationConfig


class TemperatureInference:
    """温度推理引擎"""
    
    def __init__(self, 
                 model_path: str = "physics_inspired_model_best.pth",
                 device: str = "cpu"):
        """
        初始化推理引擎
        
        参数:
            model_path: 模型文件路径
            device: 计算设备 ("cpu" 或 "cuda")
        """
        self.model_path = Path(model_path)
        self.device = torch.device(device)
        
        # 配置
        self.config = SimulationConfig()
        
        # 模型
        self.model = None
        
        # 热敏电阻参数
        self.Z0 = 50.0       # 特征阻抗 (Ω)
        self.R25 = 330.0     # 25°C时的阻值 (Ω)
        self.beta = 3500.0   # B常数 (K)
        
    def load_model(self):
        """加载模型"""
        print(f"正在加载模型: {self.model_path}")
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {self.model_path}")
        
        # 创建模型
        self.model = StructuredSolver(self.config).to(self.device)
        
        # 加载权重
        state_dict = torch.load(self.model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        
        # 设置为评估模式
        self.model.eval()
        
        print(f"✓ 模型加载成功 (设备: {self.device})")
        
    def gamma_to_temperature(self, gamma: float) -> Tuple[float, bool]:
        """
        反射系数转温度
        
        参数:
            gamma: 反射系数 [-1, 1]
            
        返回:
            temperature: 温度 (°C)
            valid: 是否有效
        """
        # 检查范围
        if not np.isfinite(gamma):
            return np.nan, False
        
        # 限制到合理范围
        if gamma < -0.999 or gamma > 0.999:
            gamma = np.clip(gamma, -0.999, 0.999)
        
        try:
            # 反射系数 → 电阻
            R = self.Z0 * (1.0 - gamma) / (1.0 + gamma)
            
            if R <= 0:
                return np.nan, False
            
            # 电阻 → 温度
            T0_kelvin = 298.15  # 25°C
            inv_T = (1.0 / T0_kelvin) + (1.0 / self.beta) * np.log(R / self.R25)
            T_kelvin = 1.0 / inv_T
            T_celsius = T_kelvin - 273.15
            
            # 检查温度合理性 (-40 ~ 150°C)
            if T_celsius < -40 or T_celsius > 150:
                return T_celsius, False
            
            return T_celsius, True
            
        except Exception as e:
            print(f"温度计算错误: {e}")
            return np.nan, False
    
    def infer(self, input_data: np.ndarray) -> Dict:
        """
        执行推理
        
        参数:
            input_data: (5, 2, 4, 64) float32
            
        返回:
            result: 字典包含
                - gamma: (4,) 反射系数
                - temperatures: (4,) 温度 (°C)
                - valid_flags: (4,) bool, 是否有效
                - H_abs: (4, 4) 信道幅度矩阵
        """
        if self.model is None:
            raise RuntimeError("模型未加载, 请先调用load_model()")
        
        # 数据验证
        if input_data.shape != (5, 2, 4, 64):
            raise ValueError(f"输入形状错误: 期望(5,2,4,64), 实际{input_data.shape}")
        
        # 转换为PyTorch张量
        input_tensor = torch.from_numpy(input_data).unsqueeze(0).to(self.device)  # (1, 5, 2, 4, 64)
        
        # 推理
        with torch.no_grad():
            output = self.model(input_tensor)  # (1, 20)
        
        # 转为NumPy
        output_np = output.squeeze(0).cpu().numpy()  # (20,)
        
        # 解析输出
        gamma = output_np[:4]          # 反射系数
        H_abs_flat = output_np[4:20]   # 信道幅度 (展平)
        H_abs = H_abs_flat.reshape(4, 4)
        
        # 转换为温度
        temperatures = []
        valid_flags = []
        
        for i in range(4):
            temp, valid = self.gamma_to_temperature(gamma[i])
            temperatures.append(temp)
            valid_flags.append(valid)
        
        # 构建结果字典
        result = {
            'gamma': gamma,
            'temperatures': np.array(temperatures),
            'valid_flags': np.array(valid_flags),
            'H_abs': H_abs,
            'raw_output': output_np
        }
        
        return result
    
    def print_result(self, result: Dict):
        """打印推理结果"""
        print("\n" + "="*60)
        print("推理结果")
        print("="*60)
        
        print("\n反射系数 Γ:")
        for i, gamma in enumerate(result['gamma']):
            print(f"  标签[{i}]: Γ = {gamma:8.4f}")
        
        print("\n温度 (°C):")
        for i, (temp, valid) in enumerate(zip(result['temperatures'], result['valid_flags'])):
            status = "✓" if valid else "✗"
            if valid:
                print(f"  标签[{i}]: T = {temp:6.2f} °C  {status}")
            else:
                print(f"  标签[{i}]: 无效  {status}")
        
        print("\n信道幅度 |H|:")
        for r in range(4):
            print(f"  天线[{r}]: ", end="")
            for t in range(4):
                print(f"{result['H_abs'][r, t]:6.3f} ", end="")
            print()
        
        print("="*60)


def test_inference():
    """测试推理功能"""
    print("="*60)
    print("推理模块测试")
    print("="*60)
    
    # 创建推理引擎
    engine = TemperatureInference(
        model_path="physics_inspired_model_best.pth",
        device="cpu"
    )
    
    try:
        # 加载模型
        engine.load_model()
        
        # 生成测试数据 (随机I/Q数据)
        print("\n生成测试输入...")
        test_input = np.random.randn(5, 2, 4, 64).astype(np.float32) * 0.3
        print(f"✓ 输入形状: {test_input.shape}")
        print(f"  数据范围: [{test_input.min():.3f}, {test_input.max():.3f}]")
        
        # 执行推理
        print("\n执行推理...")
        import time
        start_time = time.time()
        
        result = engine.infer(test_input)
        
        inference_time = (time.time() - start_time) * 1000  # ms
        print(f"✓ 推理完成 (耗时: {inference_time:.2f} ms)")
        
        # 打印结果
        engine.print_result(result)
        
        # 测试反射系数转温度
        print("\n测试反射系数转温度:")
        test_gammas = [-0.8, -0.4, 0.0, 0.4, 0.8]
        for g in test_gammas:
            temp, valid = engine.gamma_to_temperature(g)
            status = "✓" if valid else "✗"
            print(f"  Γ = {g:5.2f} → T = {temp:6.2f} °C  {status}")
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    test_inference()

