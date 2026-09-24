# KaTeX 0.18.9 (로컬 동봉)

출처: npm `katex@0.18.9` (`dist/`). MIT 라이선스(`LICENSE`).

- `katex.min.js`, `katex.min.css`: 원본 그대로
- `fonts/`: woff2만 동봉. CSS의 woff·ttf 경로는 파일이 없지만 브라우저가 woff2를 먼저 쓰므로 문제없다.

`tex.py`는 Playwright 헤드리스 브라우저에 이 파일을 올려 `katex.renderToString`으로 수식을 미리 조판한다.
결과 HTML에는 `katex.min.css`를 템플릿의 KaTeX SLOT 자리에 `<style>`로 넣고, 폰트는 base64로 내장하거나
`fonts/`를 결과물 옆에 복사한다(결정은 build 구현 시).

업데이트: https://registry.npmjs.org/katex/-/katex-<버전>.tgz 를 받아 위 파일만 교체.
