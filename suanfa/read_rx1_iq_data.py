"""
RX1 数据采集模块

功能:
- 从AD9361的RX1接口读取I/Q数据
- 缓冲并重塑为算法输入格式
- 支持连续采集和单次采集模式

作者: AI Assistant
日期: 2025-11-05
"""

import numpy as np
import iio
import time
from typing import Tuple, Optional


class RX1DataReader:
    """AD9361 RX1数据读取器"""
    
    def __init__(self, 
                 uri: str = "local:",
                 rx_freq: int = 2400000000,
                 sample_rate: int = 2000000,
                 buffer_size: int = 2560):
        """
        初始化RX1数据读取器
        
        参数:
            uri: IIO设备URI ("local:" 或 "ip:192.168.x.x")
            rx_freq: RX频率 (Hz)
            sample_rate: 采样率 (Hz)
            buffer_size: 缓冲区大小 (采样点数)
        """
        self.uri = uri
        self.rx_freq = rx_freq
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        
        # IIO上下文和设备
        self.ctx = None
        self.phy = None
        self.rxadc = None
        self.rx_buf = None
        
        # 通道
        self.rx_i = None
        self.rx_q = None
        
    def open(self):
        """打开IIO设备并配置"""
        print(f"正在连接到IIO设备: {self.uri}")
        
        # 创建IIO上下文
        try:
            self.ctx = iio.Context(self.uri)
        except Exception as e:
            raise RuntimeError(f"无法连接到IIO设备: {e}")
        
        print(f"✓ 已连接 (libiio版本: {iio.version})")
        
        # 获取AD9361-PHY设备 (用于配置)
        try:
            self.phy = self.ctx.find_device("ad9361-phy")
            if self.phy is None:
                raise RuntimeError("未找到ad9361-phy设备")
        except Exception as e:
            raise RuntimeError(f"无法找到PHY设备: {e}")
        
        # 获取ADC设备 (用于数据采集)
        try:
            self.rxadc = self.ctx.find_device("cf-ad9361-lpc")
            if self.rxadc is None:
                raise RuntimeError("未找到cf-ad9361-lpc设备")
        except Exception as e:
            raise RuntimeError(f"无法找到ADC设备: {e}")
        
        print("✓ 已找到AD9361设备")
        
        # 配置RX参数 (如果需要在代码中配置)
        # 注: 通常通过ad9361_setup.sh预先配置
        # self._configure_rx()
        
        # 获取RX I/Q通道
        self.rx_i = self.rxadc.find_channel("voltage0", False)  # RX1_I
        self.rx_q = self.rxadc.find_channel("voltage1", False)  # RX1_Q
        
        if self.rx_i is None or self.rx_q is None:
            raise RuntimeError("无法找到RX1的I/Q通道")
        
        # 使能通道
        self.rx_i.enabled = True
        self.rx_q.enabled = True
        
        # 创建缓冲区
        self.rx_buf = iio.Buffer(self.rxadc, self.buffer_size, False)
        
        print(f"✓ 已创建缓冲区 (大小: {self.buffer_size})")
        print("✓ RX1数据读取器已就绪")
        
    def close(self):
        """关闭设备"""
        if self.rx_buf:
            del self.rx_buf
        if self.ctx:
            del self.ctx
        print("✓ 已关闭IIO设备")
    
    def read_single_frame(self) -> np.ndarray:
        """
        读取单帧数据
        
        返回:
            iq_data: (2560,) 复数数组, 格式为 I + jQ
        """
        if self.rx_buf is None:
            raise RuntimeError("设备未打开, 请先调用open()")
        
        # 刷新缓冲区
        self.rx_buf.refill()
        
        # 读取I通道数据
        i_data = np.frombuffer(self.rx_i.read(self.rx_buf), dtype=np.int16)
        
        # 读取Q通道数据
        q_data = np.frombuffer(self.rx_q.read(self.rx_buf), dtype=np.int16)
        
        # 合并为复数 (I + jQ)
        iq_complex = i_data.astype(np.float32) + 1j * q_data.astype(np.float32)
        
        # 归一化 (12位ADC, 范围: -2048 ~ 2047)
        iq_normalized = iq_complex / 2048.0
        
        return iq_normalized
    
    def read_formatted_input(self) -> np.ndarray:
        """
        读取并格式化为算法输入格式
        
        返回:
            input_tensor: (5, 2, 4, 64) float32
                - 5帧 (4导频 + 1数据)
                - 2通道 (I, Q)
                - 4天线
                - 64采样点
        """
        # 读取原始I/Q数据
        iq_data = self.read_single_frame()  # (2560,) complex
        
        if len(iq_data) != 2560:
            raise ValueError(f"数据长度错误: 期望2560, 实际{len(iq_data)}")
        
        # 分离I和Q
        i_data = iq_data.real  # (2560,)
        q_data = iq_data.imag  # (2560,)
        
        # 重塑为 (5帧, 4天线, 64采样点)
        # 假设数据按照 [帧0天线0, 帧0天线1, ..., 帧4天线3] 顺序排列
        i_reshaped = i_data.reshape(5, 4, 64)  # (5, 4, 64)
        q_reshaped = q_data.reshape(5, 4, 64)  # (5, 4, 64)
        
        # 合并I和Q作为通道维度
        iq_stacked = np.stack([i_reshaped, q_reshaped], axis=1)  # (5, 2, 4, 64)
        
        return iq_stacked.astype(np.float32)
    
    def continuous_read(self, callback, interval: float = 0.05):
        """
        连续读取数据并调用回调函数
        
        参数:
            callback: 回调函数, 签名为 callback(iq_data: np.ndarray)
            interval: 读取间隔 (秒)
        """
        print(f"开始连续读取 (间隔: {interval}s)")
        
        try:
            while True:
                # 读取数据
                iq_data = self.read_formatted_input()
                
                # 调用回调
                callback(iq_data)
                
                # 等待
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n✓ 用户中断, 停止读取")
        except Exception as e:
            print(f"\n✗ 读取错误: {e}")
            raise


def test_rx1_reader():
    """测试RX1数据读取"""
    print("="*60)
    print("RX1数据读取测试")
    print("="*60)
    
    # 创建读取器
    reader = RX1DataReader()
    
    try:
        # 打开设备
        reader.open()
        
        # 读取单帧数据
        print("\n读取单帧数据...")
        iq_data = reader.read_single_frame()
        print(f"✓ 原始数据形状: {iq_data.shape}")
        print(f"  数据范围: [{iq_data.real.min():.3f}, {iq_data.real.max():.3f}]")
        print(f"  平均功率: {np.mean(np.abs(iq_data)**2):.6f}")
        
        # 读取格式化输入
        print("\n读取格式化输入...")
        input_tensor = reader.read_formatted_input()
        print(f"✓ 输入张量形状: {input_tensor.shape}")
        print(f"  数据范围: [{input_tensor.min():.3f}, {input_tensor.max():.3f}]")
        
        # 显示各帧的统计信息
        print("\n各帧统计:")
        for frame_idx in range(5):
            frame_data = input_tensor[frame_idx]
            frame_label = f"导频{frame_idx}" if frame_idx < 4 else "数据帧"
            print(f"  {frame_label}: 均值={frame_data.mean():.4f}, "
                  f"标准差={frame_data.std():.4f}")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 关闭设备
        reader.close()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    test_rx1_reader()

