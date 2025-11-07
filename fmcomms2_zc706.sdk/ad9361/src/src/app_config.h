/***************************************************************************//**
 *   @file   app_config.h
 *   @brief  Config file of AD9361/API Driver.
 *   @author DBogdan (dragos.bogdan@analog.com)
********************************************************************************
 * Copyright 2015(c) Analog Devices, Inc.
 *
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *  - Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  - Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the
 *    distribution.
 *  - Neither the name of Analog Devices, Inc. nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *  - The use of this software may or may not infringe the patent rights
 *    of one or more patent holders.  This license does not release you
 *    from the requirement that you obtain separate licenses from these
 *    patent holders to use this software.
 *  - Use of the software either in source or binary form, must be run
 *    on or directly connected to an Analog Devices Inc. component.
 *
 * THIS SOFTWARE IS PROVIDED BY ANALOG DEVICES "AS IS" AND ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, NON-INFRINGEMENT,
 * MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
 * IN NO EVENT SHALL ANALOG DEVICES BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, INTELLECTUAL PROPERTY RIGHTS, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************/
#ifndef CONFIG_H_
#define CONFIG_H_

/* 为无源反向散射通信应用配置的宏定义 */
#define HAVE_SPLIT_GAIN_TABLE	0 /* 设置为0，因为在main.c中split_gain_table_mode_enable = 0 */
#define HAVE_TDD_SYNTH_TABLE	0 /* 设置为0，因为我们使用FDD模式而非TDD模式 */

#define AD9361_DEVICE			1 /* 使用AD9361设备 */
#define AD9364_DEVICE			0
#define AD9363A_DEVICE			0

/* 平台配置 - 使用条件编译避免重复定义 */
#ifndef WINDOWS_PLATFORM
#define XILINX_PLATFORM
//#define ALTERA_PLATFORM
//#define LINUX_PLATFORM
#endif
//#define FMCOMMS5
//#define ADI_RF_SOM
//#define ADI_RF_SOM_CMOS

/* 功能启用配置 */
#define ADC_DMA_EXAMPLE        /* 启用ADC DMA传输，用于接收反向散射信号 */
//#define DAC_DMA_EXAMPLE       /* 禁用DAC DMA，因为我们使用DDS模式而不是DMA模式 */
//#define ADC_DMA_IRQ_EXAMPLE    /* 不使用中断模式，使用轮询方式更适合定时查询 */
//#define AXI_ADC_NOT_PRESENT
//#define TDD_SWITCH_STATE_EXAMPLE /* 不使用TDD切换，我们使用FDD模式 */

//#define IIO_SUPPORT /* 不使用IIO支持，简化配置 */

#ifndef IIO_SUPPORT
#define HAVE_VERBOSE_MESSAGES /* Recommended during development prints errors and warnings */
//#define HAVE_DEBUG_MESSAGES /* For Debug purposes only */
#endif // USE_LIBIIO
/*
 * In case memory footprint is a concern these options allow
 * to disable unused functionality which may free up a few kb
 */
#endif
