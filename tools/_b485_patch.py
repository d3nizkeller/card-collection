#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b485: тамагочи оживает — много анимаций (владелец: «скучно смотрится, где анимации»).

Заявка владельца (скриншот панели): «тамогочи скучно смотрится геде анимацыя
нужно очень многа анимаый».

Разбор
------
Панель b483 рисовала статичную морду-эмодзи и плоские полоски: между
действиями питомец «мертв», реакции на кормление/игру нет, опыт и полосы
меняются скачком. В проекте уже есть живые CSS-анимации для карт (fx-*, ауры,
confetti), тамагочи жил без них.

Лечение (CSS-кейфреймы в assets/app.css + крючки в renderTamagotchi/tamaAct)
---------------------------------------------------------------------------
1.Idle: питомец ДЫШИТ и покачивается (tama-bob 3s infinite) над мягкой тенью,
  которая дышит в противофазе (tama-shadow), позади — пульсирующее изумрудное
  свечение (tama-glow). Болен — отдельное покачивание + десатурация
  (tama-sick), яйцо на витрине тоже покачивается (tama-pet).
2. Реакции на действия: одноразовый класс tama-act-<действие> на морде:
  корм — чавканье (squash/stretch tama-chomp), игра — прыжок с поворотом
  (tama-jump), мытьё — виляние (tama-wiggle), сон — укачивание (tama-sway),
  лечение/появление — пружинный pop (tama-pop). Класс ставится на один
  рендер (TAMA_ANIM) и не зацикливается.
3. Частицы: tamaSpawnFx(kind) сыплет 7 эмодзи-искр над питомцем
  (еда/игры/пузыри/zzz/таблетки/подарки), каждая летит вверх с рандомным
  x/размером/задержкой (tama-fly) и сама удаляется. На уровень — вторая волна
  частиц + общий конфетти launchConfetti(60), как во вскрытии пака.
4. Полоски: .tama-bar/.tama-bar-fill — ширина едет плавно
  (transition .6s cubic-bezier), поверх бесконечный стеклянный блик
  (::after, tama-shine); полоса опыта — тот же плавный переход
  (.tama-xp-fill). Кнопки действий: hover-подъём и active-сжатие (.tama-btn).
5. prefers-reduced-motion: все бесконечные анимации тамагочи отключаются —
   вестибулярка важнее красоты.

Менялись assets/app.css и assets/app.js — тег сборки nxmob228 -> nxmob229.

Проверка/применение:
    python3 tools/_b485_patch.py --check
    python3 tools/_b485_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob228'
TAG_NEW = 'nxmob229'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# assets/app.css: кейфреймы и классы тамагочи
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.css', 1,
              r'''.nx-st-shield::before,.nx-st-shield .nx-st-bg{border-radius:0;clip-path:polygon(0 0,100% 0,100% 68%,50% 100%,0 68%)}''',
              r'''.nx-st-shield::before,.nx-st-shield .nx-st-bg{border-radius:0;clip-path:polygon(0 0,100% 0,100% 68%,50% 100%,0 68%)}

/* b485: тамагочи живой: idle-дыхание, реакции на действия, частицы, свечение,
   стеклянный блик полосок. Всё на CSS-кейфреймах; бесконечное отключается при
   prefers-reduced-motion. */
@media (prefers-reduced-motion: reduce){
    .tama-pet,.tama-glow,.tama-shadow,.tama-fx span,.tama-bar-fill::after{animation:none !important}
}
.tama-stage{position:relative;display:inline-block;padding:10px 14px 6px}
.tama-glow{position:absolute;inset:-6px -10px 2px;border-radius:9999px;background:radial-gradient(60% 55% at 50% 62%,rgba(52,211,153,.28),rgba(52,211,153,0) 70%);animation:tama-glow 3.6s ease-in-out infinite;pointer-events:none}
@keyframes tama-glow{0%,100%{opacity:.55;transform:scale(1)}50%{opacity:1;transform:scale(1.12)}}
.tama-pet{position:relative;display:inline-block;font-size:56px;line-height:1;animation:tama-bob 3s ease-in-out infinite;transform-origin:50% 90%}
@keyframes tama-bob{0%,100%{transform:translateY(0) rotate(-2deg)}50%{transform:translateY(-7px) rotate(2deg)}}
.tama-pet.tama-sick{animation:tama-sick 2.6s ease-in-out infinite;filter:saturate(.55) hue-rotate(-8deg)}
@keyframes tama-sick{0%,100%{transform:translateY(0) rotate(-4deg)}50%{transform:translateY(2px) rotate(4deg)}}
.tama-pet.tama-act-feed{animation:tama-chomp .9s ease}
@keyframes tama-chomp{0%{transform:scale(1)}30%{transform:scale(1.18,.82)}55%{transform:scale(.9,1.12)}75%{transform:scale(1.08,.94)}100%{transform:scale(1)}}
.tama-pet.tama-act-play{animation:tama-jump .9s cubic-bezier(.28,1.6,.42,1)}
@keyframes tama-jump{0%{transform:translateY(0)}30%{transform:translateY(-26px) rotate(-10deg)}55%{transform:translateY(0) scale(1.1,.9)}70%{transform:translateY(-12px) rotate(8deg)}100%{transform:translateY(0)}}
.tama-pet.tama-act-wash{animation:tama-wiggle .9s ease}
@keyframes tama-wiggle{0%,100%{transform:rotate(0)}20%{transform:rotate(-12deg)}40%{transform:rotate(10deg)}60%{transform:rotate(-8deg)}80%{transform:rotate(6deg)}}
.tama-pet.tama-act-sleep{animation:tama-sway 1.8s ease-in-out}
@keyframes tama-sway{0%,100%{transform:rotate(0) translateY(0)}50%{transform:rotate(6deg) translateY(4px)}}
.tama-pet.tama-act-heal,.tama-pet.tama-act-adopt{animation:tama-pop 1s cubic-bezier(.28,1.6,.42,1)}
@keyframes tama-pop{0%{transform:scale(.6)}45%{transform:scale(1.25)}70%{transform:scale(.92)}100%{transform:scale(1)}}
.tama-shadow{position:absolute;left:12%;right:12%;bottom:2px;height:10px;border-radius:9999px;background:rgba(2,6,23,.55);filter:blur(3px);animation:tama-shadow 3s ease-in-out infinite;pointer-events:none}
@keyframes tama-shadow{0%,100%{transform:scaleX(1);opacity:.55}50%{transform:scaleX(.82);opacity:.35}}
.tama-fx{position:absolute;inset:0;pointer-events:none;overflow:visible}
.tama-fx span{position:absolute;bottom:8px;font-size:18px;animation:tama-fly 1.6s ease-out forwards;opacity:0}
@keyframes tama-fly{0%{transform:translateY(6px) scale(.6) rotate(0);opacity:0}18%{opacity:1}100%{transform:translateY(-84px) scale(1.25) rotate(24deg);opacity:0}}
.tama-bar{position:relative;height:8px;border-radius:9999px;background:#1e293b;overflow:hidden}
.tama-bar-fill{position:relative;height:100%;border-radius:9999px;transition:width .6s cubic-bezier(.22,1,.36,1)}
.tama-bar-fill::after{content:'';position:absolute;inset:0;background:linear-gradient(110deg,rgba(255,255,255,0) 30%,rgba(255,255,255,.35) 50%,rgba(255,255,255,0) 70%);background-size:220% 100%;animation:tama-shine 2.6s linear infinite}
@keyframes tama-shine{from{background-position:120% 0}to{background-position:-120% 0}}
.tama-xp-fill{transition:width .6s cubic-bezier(.22,1,.36,1)}
.tama-btn{transition:transform .12s ease,background .2s ease,border-color .2s ease}
.tama-btn:hover{transform:translateY(-1px)}
.tama-btn:active{transform:scale(.94)}'''))

# --------------------------------------------------------------------------- #
# assets/app.js: одноразовая анимация + частицы
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function tamaBar(label, icon, val) {''',
              r'''        // b485: реакция морды и частицы. TAMA_ANIM живёт один рендер
        // (иначе реакция зациклилась бы при каждой перерисовке панели), частицы
        // сыплются отдельно и переживают перерисовку (сами удаляются по таймеру).
        let TAMA_ANIM = '';
        const TAMA_FX_EMOJI = {
            feed: ['🍗', '🍖', '✨'], play: ['🎮', '⭐', '✨'], wash: ['🫧', '', '🧼'],
            sleep: ['💤', '😴', '✨'], heal: ['💊', '❤', '✨'], adopt: ['🎉', '✨', '🐣'], level: ['🎉', '🎁', '⭐'],
        };
        function tamaSpawnFx(kind) {
            const host = document.getElementById('tama-fx');
            if (!host) return;
            const set = TAMA_FX_EMOJI[kind] || ['✨'];
            for (let i = 0; i < 7; i++) {
                const s = document.createElement('span');
                s.textContent = set[i % set.length];
                s.style.left = (8 + Math.random() * 84) + '%';
                s.style.animationDelay = (Math.random() * 0.5).toFixed(2) + 's';
                s.style.fontSize = (14 + Math.round(Math.random() * 10)) + 'px';
                host.appendChild(s);
                setTimeout(() => { try { s.remove(); } catch (e) {} }, 2300);
            }
        }
        function tamaBar(label, icon, val) {'''))

PAIRS.append(('assets/app.js', 1,
              r'''                <div class="h-2 rounded-full bg-slate-800 overflow-hidden"><div class="h-full ${col} rounded-full" style="width:${Math.max(0, Math.min(100, val))}%"></div></div>''',
              r'''                <div class="tama-bar"><div class="tama-bar-fill ${col}" style="width:${Math.max(0, Math.min(100, val))}%"></div></div>'''))

PAIRS.append(('assets/app.js', 1,
              r'''                    <div class="text-5xl leading-none">${tamaFace(t)}</div>''',
              r'''                    <div class="tama-stage"><!-- b485: сцена питомца: свечение, морда, тень, частицы -->
                        <i class="tama-glow"></i>
                        <div id="tama-pet" class="tama-pet${t.sick ? ' tama-sick' : ''}${TAMA_ANIM ? ' tama-act-' + TAMA_ANIM : ''}">${tamaFace(t)}</div>
                        <i class="tama-shadow"></i>
                        <div id="tama-fx" class="tama-fx"></div>
                    </div>'''))

PAIRS.append(('assets/app.js', 1,
              r'''                    <div class="mt-1 h-2 w-32 mx-auto lg:mx-0 rounded-full bg-slate-800 overflow-hidden"><div class="h-full bg-violet-500 rounded-full" style="width:${Math.min(100, Math.round((t.xp || 0) / need * 100))}%"></div></div>''',
              r'''                    <div class="mt-1 h-2 w-32 mx-auto lg:mx-0 rounded-full bg-slate-800 overflow-hidden"><div class="tama-xp-fill h-full bg-violet-500 rounded-full" style="width:${Math.min(100, Math.round((t.xp || 0) / need * 100))}%"></div></div>'''))

PAIRS.append(('assets/app.js', 1,
              r'''text-[11px] font-bold transition flex flex-col items-center gap-0.5">''',
              r'''text-[11px] font-bold tama-btn flex flex-col items-center gap-0.5">'''))

PAIRS.append(('assets/app.js', 1,
              r'''                <div class="text-5xl">🥚</div>''',
              r'''                <div class="tama-pet">🥚</div><!-- b485: яйцо тоже покачивается -->'''))

PAIRS.append(('assets/app.js', 1,
              r'''            saveState();
            try { cloudPublishSoon(); } catch (e) {}
            renderTamagotchi();
            if (gifted) showToast('🎁 Уровень ' + t.level + '! Тоша принёс карту «' + gifted + '»', 'success');''',
              r'''            saveState();
            try { cloudPublishSoon(); } catch (e) {}
            TAMA_ANIM = kind; // b485: одноразовая реакция морды на действие
            renderTamagotchi();
            TAMA_ANIM = '';
            tamaSpawnFx(kind); // b485: сноп частиц над питомцем
            if (gifted) { tamaSpawnFx('level'); try { launchConfetti(60); } catch (e) {} } // b485: уровень = праздник
            if (gifted) showToast('🎁 Уровень ' + t.level + '! Тоша принёс карту «' + gifted + '»', 'success');'''))

PAIRS.append(('assets/app.js', 1,
              r'''            showToast('🐣 Тоша вылупился! Действия тратят монеты, а за уровни питомец приносит карты альбома', 'success');
            renderTamagotchi();''',
              r'''            TAMA_ANIM = 'adopt'; // b485: появление — пружинный pop
            renderTamagotchi();
            TAMA_ANIM = '';
            tamaSpawnFx('adopt');
            showToast('🐣 Тоша вылупился! Действия тратят монеты, а за уровни питомец приносит карты альбома', 'success');'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, cnt, old, new in PAIRS:
        txt = files.get(rel) or read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        if n in txt:
            problems.append('%s: правка уже применена: %s...' % (rel, o[:60]))
            continue
        if txt.count(o) != cnt:
            problems.append('%s: якорь встретился %d раз вместо %d: %s...' % (rel, txt.count(o), cnt, o[:60]))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) or read(rel)
        if TAG_NEW in txt:
            problems.append('%s: тег уже %s' % (rel, TAG_NEW))
            continue
        if TAG_OLD not in txt:
            problems.append('%s: нет тега %s' % (rel, TAG_OLD))
            continue
        files[rel] = txt.replace(TAG_OLD, TAG_NEW)
    if problems:
        for p in problems:
            print('ПРОБЛЕМА:', p)
        return 1
    if '--check' in sys.argv:
        print('b485: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b485: тамагочи дышит, реагирует и сыплет частицами; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
