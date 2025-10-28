# Automated Mushroom Fruiting Unit (AMFU)

A Raspberry Pi-based automated environmental control system for mushroom cultivation. This project provides precise control over temperature, humidity, CO₂ levels, and lighting to create optimal fruiting conditions for various mushroom species.

![AMFU in action](mushroom_results/mushroom_growth.gif) 

## Project Overview

The AMFU is a self-contained system that automates the fruiting stage of mushroom cultivation. It features a web-based interface for remote monitoring and control, making mushroom growing more accessible and reliable for both hobbyists and small-scale growers.

## Repository Structure

### Core Software
- **Flask Application** - Friendly web interface for system control and monitoring
- **Component Libraries** - Python drivers for all sensors and actuators:
  - Temperature and humidity sensors (DS18B20, DHT22)
  - CO₂ sensor (MH-Z19B) 
  - Lighting control (Neopixel, custom LED circuits)
  - Actuator drivers (Peltier, fans, servos, humidifier)
- **Control System** - Smart environmental management that handles parameter conflicts

### Hardware Design
- **CAD Models** - 3D printable enclosure components and mounting brackets
- **PCB Designs** - Custom Raspberry Pi hat for cleaner wiring

### Documentation
- **Component Datasheets** - Technical specifications for all hardware
- **Test Results** - System performance validation
- **Timelapse Examples** - Watch your mushrooms grow!

## Key Features

- **Multi-parameter control** - Temperature, humidity, CO₂, and lighting all managed automatically
- **Web-based access** - Monitor and adjust conditions from any device
- **Real-time data logging** - Watch your environmental parameters live
- **Automated time-lapse** - Capture your mushroom's growth journey
- **Contamination control** - HEPA filtration keeps chamber isolated

## Perfect For

- Home mushroom cultivation enthusiasts
- Educators teaching controlled environment agriculture
- Small-scale specialty mushroom producers
- Anyone fascinated with environmental automation

---

*Happy growing!* 🍄
