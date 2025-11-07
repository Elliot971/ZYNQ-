import numpy as np

class SimulationConfig:
    # --- Signal Simulation Base Parameters ---
    FS = 2000000
    F_CARRIER = 2400000000  # 2.4 GHz (仅作参考，基带建模时可不使用)
    SYMBOL_RATE = 10000
    
    # --- Signal Duration & Processing ---
    WARMUP_SYMBOLS = 200
    SIM_SYMBOLS = 400
    SIM_DURATION = SIM_SYMBOLS / SYMBOL_RATE
    WARMUP_DURATION = WARMUP_SYMBOLS / SYMBOL_RATE

    # --- ADC Parameters ---
    ADC_BIT_DEPTH = 8
    ADC_VOLTAGE_RANGE = 1.0
    
    # --- Channel Model Parameters ---
    F_FADE = 10
    K_FACTOR = 0 

    # --- System Physical Layout (meters) ---
    TX_ANTENNA_POS = np.array([0, 0, 0])
    RX_ANTENNA_POS = np.array([
        [-0.15, 0, 0],
        [-0.05, 0, 0],
        [ 0.05, 0, 0],
        [ 0.15, 0, 0]
    ])
    square_center_x = 2.0
    square_center_y = 0.0
    square_center_z = 0.0
    square_spread = 0.8
    half_spread = square_spread / 2
    TAG_POS = np.array([
        [square_center_x, square_center_y - half_spread, square_center_z + half_spread],
        [square_center_x, square_center_y + half_spread, square_center_z + half_spread],
        [square_center_x, square_center_y - half_spread, square_center_z - half_spread],
        [square_center_x, square_center_y + half_spread, square_center_z - half_spread]
    ])

    # --- Multi-Tag MIMO System Dimensions ---
    NUM_TX_ANTENNAS = 1
    NUM_RX_ANTENNAS = 4
    NUM_TAGS = 4
    
    # --- Neural Network Input/Output Shape ---
    # 新方案：直接输入每个时隙、每根天线的观测幅度，形成 (5, 4) 矩阵
    # 旧方案：按时间采样的 I/Q 帧（保留参数兼容旧脚本）
    # 为使用 generate_one_frame 的 I/Q 数据集，改为 False
    USE_SLOT_AMPLITUDE_INPUT = False  # True: 使用(5,4)幅度矩阵；False: 使用按采样点的I/Q帧
    SAMPLES_PER_SLOT = 64  # 若 USE_SLOT_AMPLITUDE_INPUT=True，则此参数不参与数据生成
    NUM_PILOT_FRAMES = NUM_TAGS
    NUM_DATA_FRAMES = 1
    FRAME_SEQUENCE_LENGTH = NUM_PILOT_FRAMES + NUM_DATA_FRAMES
    
    X_ENFORCE_REAL_INTERVAL = False
    X_INTERVAL_BOUNDS = (-1.0, 1.0)
    
    # --- Noise/SNR Settings ---
    # 目标SNR（dB）。在数据生成时先确定SNR，再由数据帧x计算噪声强度
    TARGET_SNR_DB = 40.0

    # 是否在时域显式调制载波。如果做复基带建模，设为 False
    USE_CARRIER = False

    # --- Model Options ---
    # 是否冻结纯数学解的残差修正（只输出 x_pinv）
    FREEZE_MATH_CORRECTION = False

    # 物理一致性正则权重：约束 ||H_pred x_pred - y_data_rms||
    PHYS_LOSS_WEIGHT = 0.5
    
    # --- Training Parameters ---
    BATCH_SIZE = 64
    EPOCHS = 160
    LEARNING_RATE = 2e-4
    WEIGHT_DECAY = 5e-4
    LR_DECAY_PATIENCE = 6
    LR_DECAY_GAMMA = 0.5
    EARLY_STOP_PATIENCE = 12
    GRAD_CLIP_NORM = 5.0

    # 【Recommendation】 Increase samples to give the model enough data
    TRAIN_SAMPLES = 2048
    TEST_SAMPLES = 512

    # --- Physics/Math prior options ---
    # 相干求解的 Tikhonov 正则（模型与训练侧先验解使用）
    TIKHONOV_LAMBDA = 1e-3
    ADAPTIVE_LAMBDA = True
    ENABLE_DELTA_H = False
    X_IN_UNIT_INTERVAL = True

    # 训练时将模型输出与“纯数学先验解”对齐的权重（0 关闭）
    PRIOR_LOSS_WEIGHT = 0.2
