# Third-party notices

## cobe 2.0.1: world land mask (embedded in app/shell/login.html)
Source: https://github.com/shuding/cobe, npm cobe@2.0.1 (git 4fc247f673fbec28d5ae6d4798757e2bca83ed3b, tarball sha256 51e9080eafa6867224b47c9df9cd0b6d4ca0a7d6eb91f19fb9deac451efed4c9).
Used: the 256x128 equirectangular land-mask PNG that cobe embeds in dist/index.esm.js, copied byte for byte as a data URL (LAND_PNG). cobe's WebGL renderer is not used; the globe renderer, lighting, markers and arcs are our own code.

```
MIT License

Copyright (c) 2021 Shu Ding

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
