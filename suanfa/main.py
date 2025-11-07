"""
ZC706 + AD9361 温度感知系统主程序

功能:
- 整合RX1数据采集、算法推理、TX2结果发送
- 支持实时模式和测试模式
- 性能监控和日志记录

作者: AI Assistant
日期: 2025-11-05
"""

import argparse
import time
import numpy as np
from pathlib import Path
import sys

# 导入自定义模块
from read_rx1_iq_data import RX1DataReader
from run_inference import TemperatureInference
from send_tx2_result import TX2ResultSender


class TemperatureSensingSystem:
    """温度感知系统"""
    
    def __init__(self, 
                 model_path: str = "physics_inspired_model_best.pth",
                 device: str = "cpu",
                 protocol: str = "hex",
                 enable_tx: bool = True):
        """
        初始化系统
        
        参数:
            model_path: 模型文件路径
            device: 推理设备 ("cpu" 或 "cuda")
            protocol: 输出协议 ("hex" 或 "binary")
            enable_tx: 是否启用TX2发送
        """
        self.model_path = model_path
        self.device = device
        self.protocol = protocol
        self.enable_tx = enable_tx
        
        # 模块
        self.rx_reader = None
        self.inference_engine = None
        self.tx_sender = None
        
        # 性能统计
        self.stats = {
            'frames_processed': 0,
            'total_time': 0.0,
            'rx_time': 0.0,
            'inference_time': 0.0,
            'tx_time': 0.0
        }
        
    def initialize(self):
        """初始化所有模块"""
        print("\n" + "="*70)
        print("温度感知系统初始化")
        print("="*70)
        
        # 1. 初始化RX1读取器
        print("\n[1/3] 初始化RX1数据读取器...")
        self.rx_reader = RX1DataReader()
        self.rx_reader.open()
        
        # 2. 初始化推理引擎
        print("\n[2/3] 初始化推理引擎...")
        self.inference_engine = TemperatureInference(
            model_path=self.model_path,
            device=self.device
        )
        self.inference_engine.load_model()
        
        # 3. 初始化TX2发送器
        if self.enable_tx:
            print("\n[3/3] 初始化TX2发送器...")
            self.tx_sender = TX2ResultSender(protocol=self.protocol)
            self.tx_sender.open()
        else:
            print("\n[3/3] TX2发送器已禁用")
        
        print("\n" + "="*70)
        print("✅ 系统初始化完成")
        print("="*70)
        
    def cleanup(self):
        """清理资源"""
        print("\n正在清理资源...")
        
        if self.rx_reader:
            self.rx_reader.close()
        
        if self.tx_sender:
            self.tx_sender.close()
        
        print("✓ 资源清理完成")
        
    def process_single_frame(self) -> dict:
        """
        处理单帧数据
        
        返回:
            result: 处理结果字典
        """
        frame_start = time.time()
        
        # 1. 读取RX1数据
        rx_start = time.time()
        input_data = self.rx_reader.read_formatted_input()
        rx_time = time.time() - rx_start
        
        # 2. 执行推理
        inference_start = time.time()
        result = self.inference_engine.infer(input_data)
        inference_time = time.time() - inference_start
        
        # 3. 发送TX2结果
        tx_time = 0.0
        if self.enable_tx and self.tx_sender:
            tx_start = time.time()
            self.tx_sender.send(result)
            tx_time = time.time() - tx_start
        
        # 更新统计
        frame_time = time.time() - frame_start
        self.stats['frames_processed'] += 1
        self.stats['total_time'] += frame_time
        self.stats['rx_time'] += rx_time
        self.stats['inference_time'] += inference_time
        self.stats['tx_time'] += tx_time
        
        # 添加时间信息到结果
        result['timing'] = {
            'total': frame_time * 1000,      # ms
            'rx': rx_time * 1000,
            'inference': inference_time * 1000,
            'tx': tx_time * 1000
        }
        
        return result
    
    def run_single_shot(self):
        """单次模式: 处理一帧数据并退出"""
        print("\n" + "="*70)
        print("单次处理模式")
        print("="*70)
        
        try:
            result = self.process_single_frame()
            
            # 打印结果
            print("\n--- 推理结果 ---")
            print(f"\n温度 (°C):")
            for i, (temp, valid) in enumerate(zip(result['temperatures'], result['valid_flags'])):
                status = "✓" if valid else "✗"
                if valid:
                    print(f"  标签[{i}]: {temp:6.2f} °C  {status}")
                else:
                    print(f"  标签[{i}]: 无效     {status}")
            
            print(f"\n反射系数:")
            for i, gamma in enumerate(result['gamma']):
                print(f"  标签[{i}]: Γ = {gamma:7.4f}")
            
            # 性能
            print(f"\n--- 性能统计 ---")
            print(f"  RX采集:   {result['timing']['rx']:.2f} ms")
            print(f"  推理:     {result['timing']['inference']:.2f} ms")
            print(f"  TX发送:   {result['timing']['tx']:.2f} ms")
            print(f"  总耗时:   {result['timing']['total']:.2f} ms")
            
        except Exception as e:
            print(f"\n✗ 处理失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*70)
        
    def run_realtime(self, duration: float = None, interval: float = 0.05):
        """
        实时模式: 持续处理数据
        
        参数:
            duration: 运行时长 (秒), None表示无限运行
            interval: 处理间隔 (秒)
        """
        print("\n" + "="*70)
        print("实时处理模式")
        if duration:
            print(f"运行时长: {duration} 秒")
        else:
            print("运行时长: 无限 (按Ctrl+C停止)")
        print(f"处理间隔: {interval} 秒")
        print("="*70)
        
        start_time = time.time()
        
        try:
            while True:
                # 检查是否超时
                if duration and (time.time() - start_time) > duration:
                    print("\n✓ 达到运行时长，停止处理")
                    break
                
                # 处理一帧
                result = self.process_single_frame()
                
                # 打印简要信息
                frame_num = self.stats['frames_processed']
                elapsed = time.time() - start_time
                
                print(f"\n[帧 {frame_num:04d}] 耗时: {result['timing']['total']:.1f} ms | "
                      f"温度: ", end="")
                for i, (temp, valid) in enumerate(zip(result['temperatures'], result['valid_flags'])):
                    if valid:
                        print(f"T{i}={temp:5.1f}°C ", end="")
                    else:
                        print(f"T{i}=N/A ", end="")
                print()
                
                # 等待
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n✓ 用户中断")
        
        except Exception as e:
            print(f"\n\n✗ 运行时错误: {e}")
            import traceback
            traceback.print_exc()
        
        # 打印统计信息
        self.print_statistics()
        
    def print_statistics(self):
        """打印性能统计"""
        if self.stats['frames_processed'] == 0:
            return
        
        print("\n" + "="*70)
        print("性能统计")
        print("="*70)
        
        n = self.stats['frames_processed']
        
        print(f"\n处理帧数:     {n}")
        print(f"总运行时间:   {self.stats['total_time']:.2f} s")
        print(f"平均帧率:     {n / self.stats['total_time']:.2f} fps")
        
        print(f"\n平均耗时 (每帧):")
        print(f"  RX采集:     {self.stats['rx_time'] / n * 1000:.2f} ms")
        print(f"  推理:       {self.stats['inference_time'] / n * 1000:.2f} ms")
        print(f"  TX发送:     {self.stats['tx_time'] / n * 1000:.2f} ms")
        print(f"  总计:       {self.stats['total_time'] / n * 1000:.2f} ms")
        
        print("="*70)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="ZC706 + AD9361 温度感知系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 单次处理
  python main.py --mode single
  
  # 实时处理 (无限运行)
  python main.py --mode realtime
  
  # 实时处理 (运行60秒)
  python main.py --mode realtime --duration 60
  
  # 使用GPU推理
  python main.py --mode realtime --device cuda
  
  # 禁用TX2发送 (仅测试)
  python main.py --mode single --no-tx
        """
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        default='single',
        choices=['single', 'realtime'],
        help='运行模式: single (单次) 或 realtime (实时)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='physics_inspired_model_best.pth',
        help='模型文件路径'
    )
    
    parser.add_argument(
        '--device',
        type=str,
        default='cpu',
        choices=['cpu', 'cuda'],
        help='推理设备'
    )
    
    parser.add_argument(
        '--protocol',
        type=str,
        default='hex',
        choices=['hex', 'binary'],
        help='TX2输出协议'
    )
    
    parser.add_argument(
        '--duration',
        type=float,
        default=None,
        help='实时模式运行时长 (秒), 默认无限运行'
    )
    
    parser.add_argument(
        '--interval',
        type=float,
        default=0.05,
        help='实时模式处理间隔 (秒)'
    )
    
    parser.add_argument(
        '--no-tx',
        action='store_true',
        help='禁用TX2发送 (仅用于测试)'
    )
    
    args = parser.parse_args()
    
    # 打印横幅
    print("\n" + "="*70)
    print(" "*15 + "ZC706 温度感知系统")
    print(" "*20 + "v1.0")
    print("="*70)
    
    # 检查模型文件
    if not Path(args.model).exists():
        print(f"\n✗ 错误: 模型文件不存在: {args.model}")
        print("\n请确保模型文件在当前目录，或使用--model指定路径")
        sys.exit(1)
    
    # 创建系统
    system = TemperatureSensingSystem(
        model_path=args.model,
        device=args.device,
        protocol=args.protocol,
        enable_tx=not args.no_tx
    )
    
    try:
        # 初始化
        system.initialize()
        
        # 运行
        if args.mode == 'single':
            system.run_single_shot()
        else:  # realtime
            system.run_realtime(
                duration=args.duration,
                interval=args.interval
            )
        
    except Exception as e:
        print(f"\n✗ 系统错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # 清理
        system.cleanup()
    
    print("\n" + "="*70)
    print("程序结束")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

