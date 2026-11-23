# Credits & Third-Party Licenses

Clipsora is built upon and made possible by a wide array of incredible open-source projects, fonts, tools, and libraries. We do not claim ownership of any third-party work. All copyrights, trademarks, and licenses belong to their respective authors and contributors.

---

## Table of Contents

1. [Clipsora & Contributors (MIT License)](#1-clipsora--contributors)
2. [Fonts & Typography (OFL 1.1)](#2-fonts--typography)
   - [Anton](#anton)
   - [Archivo Black](#archivo-black)
   - [Poppins](#poppins)
   - [Montserrat](#montserrat)
   - [Playfair Display](#playfair-display)
   - [Geist](#geist)
   - [Google Noto Fonts](#google-noto-fonts)
3. [Core Video & Audio Engines](#3-core-video--audio-engines)
   - [FFmpeg](#ffmpeg)
   - [sherpa-onnx & NeMo Parakeet](#sherpa-onnx--nemo-parakeet)
   - [yt-dlp](#yt-dlp)
   - [Deno](#deno)
4. [Backend Framework & Python Dependencies](#4-backend-framework--python-dependencies)
   - [FastAPI](#fastapi)
   - [Starlette & Uvicorn](#starlette--uvicorn)
   - [SQLAlchemy](#sqlalchemy)
   - [Pillow (PIL Fork)](#pillow-pil-fork)
   - [HTTPX](#httpx)
   - [Pydantic](#pydantic)
   - [SoundFile](#soundfile)
   - [psycopg](#psycopg)
   - [python-multipart](#python-multipart)
5. [Infrastructure & Services](#5-infrastructure--services)
   - [Caddy Web Server](#caddy-web-server)
   - [PostgreSQL](#postgresql)
6. [Web Interface & UI Icons](#6-web-interface--ui-icons)

---

## 1. Clipsora & Contributors

```text
MIT License

Copyright (c) 2026 PeakCut contributors
Copyright (c) 2026 Clipsora contributors (https://github.com/akashp18/Clipsora)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. Fonts & Typography

### Anton
- **Authors:** Vernon Adams, The Anton Project Authors
- **Repository:** https://github.com/googlefonts/AntonFont
- **License:** SIL Open Font License, Version 1.1

```text
Copyright 2020 The Anton Project Authors (https://github.com/googlefonts/AntonFont.git)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at: http://scripts.sil.org/OFL
```

### Archivo Black
- **Authors:** Héctor Gatti, Omnibus-Type Team
- **Repository:** https://github.com/Omnibus-Type/ArchivoBlack
- **License:** SIL Open Font License, Version 1.1

```text
Copyright 2017 The Archivo Black Project Authors (https://github.com/Omnibus-Type/ArchivoBlack)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at: http://scripts.sil.org/OFL
```

### Poppins
- **Authors:** Ninad Kale, Jonny Pinhorn, Indian Type Foundry
- **Repository:** https://github.com/itfoundry/Poppins
- **License:** SIL Open Font License, Version 1.1

```text
Copyright 2020 The Poppins Project Authors (https://github.com/itfoundry/Poppins)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at: http://scripts.sil.org/OFL
```

### Montserrat
- **Authors:** Julieta Ulanovsky, Sol Matas, Juan Pablo del Peral, Jacques Le Bailly
- **Repository:** https://github.com/JulietaUla/Montserrat
- **License:** SIL Open Font License, Version 1.1

```text
Copyright 2011 The Montserrat Project Authors (https://github.com/JulietaUla/Montserrat)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at: http://scripts.sil.org/OFL
```

### Playfair Display
- **Authors:** Claus Eggers Sørensen
- **Repository:** https://github.com/clauseggers/Playfair-Display
- **License:** SIL Open Font License, Version 1.1

```text
Copyright 2017 The Playfair Display Project Authors (https://github.com/clauseggers/Playfair-Display)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at: http://scripts.sil.org/OFL
```

### Geist
- **Authors:** Vercel, Inc.
- **Repository:** https://vercel.com/font
- **License:** SIL Open Font License, Version 1.1

```text
Copyright (c) 2023 Vercel, Inc. (https://vercel.com)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at: http://scripts.sil.org/OFL
```

### Google Noto Fonts
- **Authors:** Google LLC (`fonts-noto-core`, `fonts-noto-cjk`)
- **License:** SIL Open Font License, Version 1.1

---

## 3. Core Video & Audio Engines

### FFmpeg
- **Authors:** The FFmpeg developers
- **Website:** https://ffmpeg.org
- **License:** GNU Lesser General Public License (LGPL) version 2.1+ / GNU General Public License (GPL) version 2+
- **Usage:** Handles all video extraction, resizing, audio filters, subtitle overlay, and encoding.

### sherpa-onnx & NeMo Parakeet
- **Authors:** Xiaomi Corporation, Kaldi Authors (Daniel Povey, Fangjun Kuang, et al.) & NVIDIA Corporation
- **Repositories:**
  - sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx
  - NeMo Parakeet TDT Model: https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8
- **License:** Apache License, Version 2.0

```text
Copyright (c) 2022-2026 Xiaomi Corporation
Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
```

### yt-dlp
- **Authors:** yt-dlp contributors
- **Repository:** https://github.com/yt-dlp/yt-dlp
- **License:** Unlicense / Public Domain / MIT License
- **Usage:** Media scraping and stream downloads for supported platforms.

### Deno
- **Authors:** The Deno Authors
- **Repository:** https://github.com/denoland/deno
- **License:** MIT License

```text
Copyright 2018-2026 the Deno authors. All rights reserved. MIT License.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 4. Backend Framework & Python Dependencies

### FastAPI
- **Author:** Sebastián Ramírez (@tiangolo)
- **Repository:** https://github.com/fastapi/fastapi
- **License:** MIT License

```text
Copyright (c) 2018 Sebastián Ramírez

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

### Starlette & Uvicorn
- **Authors:** Encode OSS Ltd.
- **Repositories:**
  - Starlette: https://github.com/encode/starlette
  - Uvicorn: https://github.com/encode/uvicorn
- **License:** BSD 3-Clause License

```text
Copyright © 2017-2026, Encode OSS Ltd. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice...
```

### SQLAlchemy
- **Author:** Michael Bayer
- **Website:** https://www.sqlalchemy.org
- **License:** MIT License

```text
Copyright 2005-2026 Michael Bayer.

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software...
```

### Pillow (PIL Fork)
- **Authors:** Alex Clark and contributors; Fredrik Lundh, Secret Labs AB
- **Website:** https://python-pillow.org
- **License:** Historical Permission Notice and Disclaimer (HPND License / MIT-like)

```text
The Python Imaging Library (PIL) is

    Copyright © 1997-2011 by Secret Labs AB
    Copyright © 1995-2011 by Fredrik Lundh
    Copyright © 2010-2026 by Alex Clark and contributors

Like PIL, Pillow is licensed under the open source HPND License.
```

### HTTPX
- **Authors:** Encode OSS Ltd.
- **Repository:** https://github.com/encode/httpx
- **License:** BSD 3-Clause License

```text
Copyright © 2019-2026 Encode OSS Ltd. All rights reserved.
```

### Pydantic
- **Author:** Samuel Colvin and contributors
- **Repository:** https://github.com/pydantic/pydantic
- **License:** MIT License

```text
Copyright (c) 2017-2026 Samuel Colvin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software")...
```

### SoundFile
- **Authors:** Bastian Bechtold and contributors
- **Repository:** https://github.com/bastibe/python-soundfile
- **License:** BSD 3-Clause License

```text
Copyright (c) 2013-2026, Bastian Bechtold. All rights reserved.
```

### psycopg
- **Authors:** Federico Di Gregorio, Daniele Varrazzo
- **Website:** https://www.psycopg.org/
- **License:** GNU Lesser General Public License (LGPL) / BSD-compatible binary wrappers

### python-multipart
- **Author:** Andrew Dunham
- **Repository:** https://github.com/Kludex/python-multipart
- **License:** Apache License, Version 2.0

---

## 5. Infrastructure & Services

### Caddy Web Server
- **Authors:** Matthew Holt and The Caddy Authors
- **Website:** https://caddyserver.com
- **License:** Apache License, Version 2.0

### PostgreSQL
- **Authors:** PostgreSQL Global Development Group
- **Website:** https://www.postgresql.org
- **License:** PostgreSQL License (compatible with MIT / BSD)

```text
PostgreSQL Database Management System
(formerly known as Postgres, then as Postgres95)

Portions Copyright (c) 1996-2026, PostgreSQL Global Development Group
Portions Copyright (c) 1994, The Regents of the University of California
```

---

## 6. Web Interface & UI Icons

- The SVG icon design language uses clean line icons inspired by open-source systems such as **[Feather Icons](https://feathericons.com)** and **[Lucide Icons](https://lucide.dev)** (both MIT Licensed, Copyright (c) Cole Bemis and Lucide Contributors).
- Design tokens and color spaces are maintained in `web/tokens.css`.
