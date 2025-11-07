################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../src/src/platform/axi_io.c \
../src/src/platform/delay.c \
../src/src/platform/gpio.c \
../src/src/platform/irq.c \
../src/src/platform/spi.c \
../src/src/platform/xilinx_gpio.c \
../src/src/platform/xilinx_spi.c 

OBJS += \
./src/src/platform/axi_io.o \
./src/src/platform/delay.o \
./src/src/platform/gpio.o \
./src/src/platform/irq.o \
./src/src/platform/spi.o \
./src/src/platform/xilinx_gpio.o \
./src/src/platform/xilinx_spi.o 

C_DEPS += \
./src/src/platform/axi_io.d \
./src/src/platform/delay.d \
./src/src/platform/gpio.d \
./src/src/platform/irq.d \
./src/src/platform/spi.d \
./src/src/platform/xilinx_gpio.d \
./src/src/platform/xilinx_spi.d 


# Each subdirectory must supply rules for building sources it contributes
src/src/platform/%.o: ../src/src/platform/%.c
	@echo 'Building file: $<'
	@echo 'Invoking: ARM v7 gcc compiler'
	arm-none-eabi-gcc -DXILINX_PLATFORM -Wall -O0 -g3 -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src\platform" -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src\ad9361" -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src\axi_core" -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src\include" -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src" -c -fmessage-length=0 -MT"$@" -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -I../../ad9361_bsp/ps7_cortexa9_0/include -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -o "$@" "$<"
	@echo 'Finished building: $<'
	@echo ' '


