################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../src/src/axi_core/axi_adc_core.c \
../src/src/axi_core/axi_dac_core.c \
../src/src/axi_core/axi_dmac.c 

OBJS += \
./src/src/axi_core/axi_adc_core.o \
./src/src/axi_core/axi_dac_core.o \
./src/src/axi_core/axi_dmac.o 

C_DEPS += \
./src/src/axi_core/axi_adc_core.d \
./src/src/axi_core/axi_dac_core.d \
./src/src/axi_core/axi_dmac.d 


# Each subdirectory must supply rules for building sources it contributes
src/src/axi_core/%.o: ../src/src/axi_core/%.c
	@echo 'Building file: $<'
	@echo 'Invoking: ARM v7 gcc compiler'
	arm-none-eabi-gcc -DXILINX_PLATFORM -Wall -O0 -g3 -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src\platform" -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src\ad9361" -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src\axi_core" -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src\include" -I"C:\Users\Elliot\Desktop\FPGA\FPGA2\hdl-hdl_2019_r2\projects\fmcomms2\zc706\fmcomms2_zc706.sdk\ad9361\src\src" -c -fmessage-length=0 -MT"$@" -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -I../../ad9361_bsp/ps7_cortexa9_0/include -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@)" -o "$@" "$<"
	@echo 'Finished building: $<'
	@echo ' '


