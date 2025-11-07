"""
TX2 结果发送模块

功能:
- 将温度结果编码为十六进制协议
- 通过AD9361的TX2接口发送
- 支持多种协议格式

作者: AI Assistant
日期: 2025-11-05
"""

import numpy as np
import iio
import struct
from typing import List, Dict


class TX2ResultSender:
    """TX2结果发送器"""
    
    def __init__(self,
                 uri: str = "local:",
                 tx_freq: int = 2400000000,
                 sample_rate: int = 1000000,
                 protocol: str = "hex"):
        """
        初始化TX2发送器
        
        参数:
            uri: IIO设备URI
            tx_freq: TX频率 (Hz)
            sample_rate: 采样率 (Hz)
            protocol: 协议类型 ("hex", "binary", "json")
        """
        self.uri = uri
        self.tx_freq = tx_freq
        self.sample_rate = sample_rate
        self.protocol = protocol
        
        # IIO上下文和设备
        self.ctx = None
        self.phy = None
        self.txdac = None
        self.tx_buf = None
        
        # 通道
        self.tx_i = None
        self.tx_q = None
        
        # 协议参数
        self.frame_header = [0xAA, 0x55]
        self.temp_scale = 10  # 温度乘以10编码 (保留1位小数)
        
    def open(self):
        """打开IIO设备"""
        print(f"正在连接到TX2设备: {self.uri}")
        
        # 创建IIO上下文
        try:
            self.ctx = iio.Context(self.uri)
        except Exception as e:
            raise RuntimeError(f"无法连接到IIO设备: {e}")
        
        # 获取PHY设备
        self.phy = self.ctx.find_device("ad9361-phy")
        if self.phy is None:
            raise RuntimeError("未找到ad9361-phy设备")
        
        # 获取DAC设备
        self.txdac = self.ctx.find_device("cf-ad9361-dds-core-lpc")
        if self.txdac is None:
            raise RuntimeError("未找到cf-ad9361-dds-core-lpc设备")
        
        print("✓ 已找到TX2设备")
        
        # 获取TX I/Q通道 (TX2 = voltage2/voltage3)
        self.tx_i = self.txdac.find_channel("voltage2", True)  # TX2_I
        self.tx_q = self.txdac.find_channel("voltage3", True)  # TX2_Q
        
        if self.tx_i is None or self.tx_q is None:
            raise RuntimeError("无法找到TX2的I/Q通道")
        
        # 使能通道
        self.tx_i.enabled = True
        self.tx_q.enabled = True
        
        # 创建缓冲区
        buffer_size = 1024  # 足够发送一帧数据
        self.tx_buf = iio.Buffer(self.txdac, buffer_size, False)
        
        print(f"✓ 已创建TX缓冲区 (大小: {buffer_size})")
        print("✓ TX2发送器已就绪")
        
    def close(self):
        """关闭设备"""
        if self.tx_buf:
            del self.tx_buf
        if self.ctx:
            del self.ctx
        print("✓ 已关闭TX2设备")
    
    def encode_hex_protocol(self, temperatures: np.ndarray, valid_flags: np.ndarray) -> bytes:
        """
        编码为十六进制协议
        
        协议格式:
        [Header(2)] [Temp0(2)] [Temp1(2)] [Temp2(2)] [Temp3(2)] [CRC(1)]
        
        参数:
            temperatures: (4,) 温度数组 (°C)
            valid_flags: (4,) 有效性标志
            
        返回:
            packet: 编码后的字节数组
        """
        packet = bytearray()
        
        # 添加帧头
        packet.extend(self.frame_header)
        
        # 添加温度数据 (每个温度2字节, 大端序)
        for i in range(4):
            if valid_flags[i]:
                # 温度乘以10并转为int16
                temp_int = int(temperatures[i] * self.temp_scale)
                # 限制范围: -400 ~ 1500 (对应 -40°C ~ 150°C)
                temp_int = max(-400, min(1500, temp_int))
            else:
                # 无效数据标记为0xFFFF
                temp_int = 0xFFFF
            
            # 大端序编码 (高字节在前)
            packet.append((temp_int >> 8) & 0xFF)   # 高字节
            packet.append(temp_int & 0xFF)          # 低字节
        
        # 计算CRC (简单的异或校验)
        crc = 0
        for byte in packet:
            crc ^= byte
        packet.append(crc)
        
        return bytes(packet)
    
    def encode_binary_protocol(self, result: Dict) -> bytes:
        """
        编码为二进制协议 (包含反射系数和温度)
        
        参数:
            result: 推理结果字典
            
        返回:
            packet: 二进制数据包
        """
        packet = bytearray()
        
        # 帧头
        packet.extend(self.frame_header)
        
        # 数据类型标识 (0x01 = 完整数据)
        packet.append(0x01)
        
        # 反射系数 (4 × float32 = 16字节)
        for gamma in result['gamma']:
            packet.extend(struct.pack('<f', gamma))  # 小端序float32
        
        # 温度 (4 × float32 = 16字节)
        for temp in result['temperatures']:
            packet.extend(struct.pack('<f', temp))
        
        # 有效性标志 (4字节)
        for valid in result['valid_flags']:
            packet.append(0x01 if valid else 0x00)
        
        # CRC
        crc = sum(packet) & 0xFF
        packet.append(crc)
        
        return bytes(packet)
    
    def modulate_to_iq(self, data: bytes) -> Tuple[np.ndarray, np.ndarray]:
        """
        将字节数据调制为I/Q信号 (简单的BPSK调制)
        
        参数:
            data: 字节数据
            
        返回:
            i_samples: I通道采样 (int16)
            q_samples: Q通道采样 (int16)
        """
        # 每个字节转为8个bit
        bits = []
        for byte in data:
            for bit_idx in range(8):
                bit = (byte >> (7 - bit_idx)) & 1
                bits.append(bit)
        
        # BPSK调制: bit=0 → -1, bit=1 → +1
        symbols = np.array([2*bit - 1 for bit in bits], dtype=np.float32)
        
        # 每个符号重复N次 (过采样)
        samples_per_symbol = 8
        i_samples = np.repeat(symbols, samples_per_symbol) * 1000  # 幅度1000
        
        # Q通道为0 (实信号)
        q_samples = np.zeros_like(i_samples)
        
        # 转为int16
        i_samples_int16 = i_samples.astype(np.int16)
        q_samples_int16 = q_samples.astype(np.int16)
        
        return i_samples_int16, q_samples_int16
    
    def send(self, result: Dict):
        """
        发送结果
        
        参数:
            result: 推理结果字典
        """
        if self.tx_buf is None:
            raise RuntimeError("设备未打开, 请先调用open()")
        
        # 根据协议类型编码
        if self.protocol == "hex":
            packet = self.encode_hex_protocol(
                result['temperatures'], 
                result['valid_flags']
            )
        elif self.protocol == "binary":
            packet = self.encode_binary_protocol(result)
        else:
            raise ValueError(f"不支持的协议类型: {self.protocol}")
        
        # 打印发送的数据包
        hex_str = " ".join(f"{b:02X}" for b in packet)
        print(f"发送数据包: {hex_str} ({len(packet)} 字节)")
        
        # 调制为I/Q信号
        i_samples, q_samples = self.modulate_to_iq(packet)
        
        # 写入缓冲区
        # 注: 这里简化了发送流程，实际使用时需要根据硬件调整
        try:
            # 准备数据 (交错I/Q)
            iq_interleaved = np.empty(len(i_samples) * 2, dtype=np.int16)
            iq_interleaved[0::2] = i_samples
            iq_interleaved[1::2] = q_samples
            
            # 截断或填充到缓冲区大小
            buffer_size = self.tx_buf.samples_count * 2  # I+Q
            if len(iq_interleaved) < buffer_size:
                # 填充零
                iq_padded = np.zeros(buffer_size, dtype=np.int16)
                iq_padded[:len(iq_interleaved)] = iq_interleaved
                iq_interleaved = iq_padded
            else:
                # 截断
                iq_interleaved = iq_interleaved[:buffer_size]
            
            # 写入
            self.tx_i.write(self.tx_buf, iq_interleaved[0::2].tobytes())
            self.tx_q.write(self.tx_buf, iq_interleaved[1::2].tobytes())
            
            # 推送到硬件
            self.tx_buf.push()
            
            print("✓ 数据已发送到TX2")
            
        except Exception as e:
            print(f"✗ 发送失败: {e}")
            raise


def test_tx2_sender():
    """测试TX2发送功能"""
    print("="*60)
    print("TX2发送模块测试")
    print("="*60)
    
    # 创建模拟结果
    result = {
        'gamma': np.array([0.35, -0.12, 0.67, -0.44]),
        'temperatures': np.array([28.5, 34.2, 42.8, 52.1]),
        'valid_flags': np.array([True, True, True, True]),
        'H_abs': np.ones((4, 4))
    }
    
    # 创建发送器
    sender = TX2ResultSender(protocol="hex")
    
    # 测试编码 (不实际发送)
    print("\n测试协议编码...")
    
    # Hex协议
    hex_packet = sender.encode_hex_protocol(result['temperatures'], result['valid_flags'])
    print(f"\nHex协议数据包:")
    print(f"  {' '.join(f'{b:02X}' for b in hex_packet)}")
    print(f"  长度: {len(hex_packet)} 字节")
    
    # 解析显示
    print(f"\n解析:")
    print(f"  帧头: {hex_packet[0]:02X} {hex_packet[1]:02X}")
    for i in range(4):
        temp_bytes = hex_packet[2 + i*2:4 + i*2]
        temp_int = (temp_bytes[0] << 8) | temp_bytes[1]
        if temp_int == 0xFFFF:
            print(f"  温度{i}: 无效")
        else:
            temp_celsius = temp_int / 10.0
            print(f"  温度{i}: 0x{temp_int:04X} = {temp_celsius:.1f} °C")
    print(f"  CRC: {hex_packet[-1]:02X}")
    
    # Binary协议
    binary_packet = sender.encode_binary_protocol(result)
    print(f"\nBinary协议数据包:")
    print(f"  {' '.join(f'{b:02X}' for b in binary_packet[:20])}... (前20字节)")
    print(f"  长度: {len(binary_packet)} 字节")
    
    # 测试调制
    print("\n测试I/Q调制...")
    i_samples, q_samples = sender.modulate_to_iq(hex_packet)
    print(f"  I通道采样数: {len(i_samples)}")
    print(f"  Q通道采样数: {len(q_samples)}")
    print(f"  I范围: [{i_samples.min()}, {i_samples.max()}]")
    
    print("\n" + "="*60)
    print("测试完成 (未实际发送到硬件)")
    print("="*60)


if __name__ == "__main__":
    test_tx2_sender()

