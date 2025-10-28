# Automated Mushroom Fruiting Unit (AMFU)

A Raspberry Pi-based automated environmental control system for mushroom cultivation. This project provides precise control over temperature, humidity, CO₂ levels, and lighting to create optimal fruiting conditions for various mushroom species.

![AMFU in action](mushroom_results/mushroom_growth.gif) 

## Project Overview

The AMFU is a self-contained system that automates the most challenging aspects of mushroom cultivation during the fruiting stage. It features a web-based interface for remote monitoring and control, making mushroom growing more accessible and reliable for both hobbyists and small-scale growers.

Think of it as a smart incubator that maintains perfect growing conditions 24/7, so you can focus on enjoying the harvest rather than constantly adjusting parameters!

## Repository Structure

### Core Software
- **Flask Application** - Friendly web interface for system control and monitoring
- **Component Libraries** - Python drivers for all sensors and actuators:
  - Temperature sensors (DS18B20, DHT22)
  - CO₂ sensor (MH-Z19B) 
  - Lighting control (Neopixel, custom LED circuits)
  - Actuator drivers (Peltier, fans, servos, humidifier)
- **Control System** - Smart environmental management that prevents parameter conflicts

### Hardware Design
- **CAD Models** - 3D printable enclosure components and mounting brackets
- **PCB Designs** - Custom Raspberry Pi hat for cleaner wiring
- **Circuit Diagrams** - Complete electrical schematics

### Documentation
- **Component Datasheets** - Technical specifications for all hardware
- **Assembly Guide** - Step-by-step build instructions
- **Test Results** - System performance validation
- **Timelapse Examples** - Watch your mushrooms grow!

## Key Features

- **Multi-parameter control** - Temperature, humidity, CO₂, and lighting all managed automatically
- **Web-based access** - Monitor and adjust conditions from any device
- **Real-time data logging** - Watch your environmental parameters in real-time
- **Automated time-lapse** - Capture your mushroom's growth journey
- **Contamination control** - HEPA filtration keeps your cultures clean
- **Smart control system** - Prevents heating and cooling from fighting each other

## Hardware Requirements

- Raspberry Pi 3B+ or newer
- Environmental sensors (temperature, humidity, CO₂)
- Peltier module for heating/cooling
- Ultrasonic humidifier
- HEPA filtration system
- Programmable lighting (white, RGB, UV spectra)
- 3D printer for custom components

## Getting Started

1. Clone the repository
2. Install Python dependencies from requirements.txt
3. Configure system parameters in config files
4. Access the web interface at your Raspberry Pi's IP address
5. Start growing mushrooms!

## Perfect For

- Home mushroom cultivation enthusiasts
- Educators teaching controlled environment agriculture
- Researchers studying fungal growth
- Small-scale specialty mushroom producers
- Anyone fascinated by the intersection of biology and technology

This project brings professional-grade environmental control to home growers, making successful mushroom cultivation achievable for everyone. Watch your mycelium thrive in perfectly maintained conditions!

---

*Happy growing! May your mushrooms be plentiful and your contamination low.* 🍄
