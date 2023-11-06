# MaaS Blender 
[![ci workflow](https://github.com/maasblender/maasblender/actions/workflows/ci.yaml/badge.svg)](https://github.com/maasblender/maasblender/actions/workflows/ci.yaml "CI status")
[![license check workflow](https://github.com/maasblender/maasblender/actions/workflows/check.yaml/badge.svg)](https://github.com/maasblender/maasblender/actions/workflows/check.yaml "License check")
[![license](https://img.shields.io/github/license/maasblender/maasblender)](LICENSE)

Core components of MaaS Blender


## Overview

MaaS Blender is an open-source multi-mobility simulation platform which aims to evaluate MaaS (Mobility as a Service) by utilizing several mobility simulators. MaaS Blender consists of following components:

- Simulation Broker
- Common Modules
- Simplified mobility simulator(s)

Each component connects by REST APIs and transfer data as mobility events.

![Overview](/doc/images/overview.png "Overview")


## Motivation

MaaS (Mobility as a Service) has rapid growth in the world and is expected to expand further.
It enables  us to move freely by using several types of mobilities.
To support it, we propose MaaS Blender, which is a new open-source multi-mobility simulation platform.
It allows decision-makers to simulate several mobility services at the same time, to evaluate which MaaS combination is best/better with several criteria.
By utilizing several simulation results with other investigations and practical limitations, 
decision-makers discuss the MaaS combination which is suitable for them and agree with all stakeholders.
 We believe that the proposed simulation platform can support further MaaS 
 which will appear in the future but has high complexities for service combinations and difficulties for service stopping easily.
This simulation platform intends to use several phases of MasS introduction, implementation and revision.
To utilize our platform in each phase, the platform shas  features that enables users to attach/detach each function owned by each mobility service provider and stakeholder.

## Contributing
If you find bugs or want to add some features, please check out the [contributing guide](CONTRIBUTING.md). 


## License

Licensed under [Apache-2.0 License](LICENSE).

## Reference

Y. Fujita, M. Kuwahara and E. Ueda, "MaaS Blender: Integration of Mobility Simulators for Mobility as a Service Evaluation," in IEEE Access, vol. 11, pp. 105105-105114, 2023, doi: 10.1109/ACCESS.2023.3319079.
[Link](https://ieeexplore.ieee.org/document/10262296)

Copyright (c) 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
