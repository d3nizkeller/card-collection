/* Прекомпиляция Tailwind для tools/build.py.
   Вместо JIT-компилятора, работающего в браузере на каждом рендере, собираем
   статику один раз. В `content` скармливается ВЕСЬ исходный index.html — так
   Tailwind находит и классы в разметке, и пулы строк в JS (${getRarityClass(...)},
   cls[o.r], meta.color и т.п.), поэтому ни один динамический класс не теряется.

   Запуск отдельно:  node tools/twbuild.js
   Требует:          npm i -D tailwindcss postcss   (в корне репозитория) */
const fs = require('fs');
const path = require('path');
const postcss = require('postcss');
const tailwindcss = require('tailwindcss');

const root = path.join(__dirname, '..');
const src = path.join(__dirname, '_tw_src.html');
if (!fs.existsSync(src)) fs.copyFileSync(path.join(root, 'index.html'), src);

const config = {
    darkMode: 'class',
    content: [src],
    theme: {
        extend: {
            colors: {
                // ровно тот же extend, что был в tailwind.config внутри index.html
                brand: { 50: '#f0fdf4', 500: '#22c55e', 600: '#16a34a', 900: '#14532d' },
            },
        },
    },
    plugins: [],
};

(async () => {
    const t0 = Date.now();
    const r = await postcss([tailwindcss(config)]).process(
        '@tailwind base;@tailwind components;@tailwind utilities;',
        { from: undefined }
    );
    const css = ('/* Tailwind CSS — прекомпилирован tools/twbuild.js из tools/_tw_src.html.\n' +
        '   НЕ редактировать вручную: пересоберите через python3 tools/build.py --tw */\n' +
        r.css.replace(/\n\s*\n/g, '\n'));
    const out = path.join(root, 'assets', 'tailwind.css');
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, css);
    console.log('tailwind.css %d КБ за %d мс (правил: %d)',
        Math.round(css.length / 1024), Date.now() - t0, (css.match(/\{/g) || []).length);
})();
