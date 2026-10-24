#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b483: новая игра в «Игры» — ТАМАГОЧИ, все действия тратят баланс.

Заявка владельца: «добавь в игры игру тамагочи чтоб все действия тратили
баланс».

Разбор
------
Во вкладке «Игры» (section#tab-battle) режимы переключаются плитками
(Арена/Дурак/Шахта/Слоты/Сетка/Линии/Мины/Колесо) и у каждого своё лобби
(#lobby-*). Тамагочи встраивается девятым режимом со своим лобби #lobby-tama:
питомец живёт в state.tamagotchi (localStorage nexus_tamagotchi), растёт от
действий и требует монет за каждое действие — ровно как просил владелец.

Механика
--------
* Яйцо стоит 100 монет (tamaAdopt): питомец «Тоша» появляется с характеристиками
  80/80/80/80. Дальше каждое действие тратит монеты из ОБЩЕГО баланса
  (state.coins → updateCoinDisplay → saveState): покормить 15, поиграть 20,
  помыть 10, уложить 5, лечить 40. Не хватает монет — действие не проходит,
  тост «Не хватает монет…».
* Характеристики (сытость/настроение/энергия/чистота) тают в реальном времени
  (TAMA_DECAY_PER_MIN), включая офлайн: tamaSync() досчитывает по lastTs, но
  не больше 12 часов (TAMA_OFFLINE_CAP_MIN) — неделя отсутствия не убивает
  питомца. Среднее ниже 25 → питомец болеет: доступен только «Лечить».
* Действия дают +10 опыта; уровень = 40 + level*20 опыта. На новом уровне
  питомец ДАРИТ случайную карту альбома (tamaGift: rollCardFromPack случайного
  пака + state.collection) — мотивация тратить монеты без возврата монет.
* Морда питомца — эмодзи по состоянию: 🥚 нет питомца, 🤒 болен, 😴 устал,
  😺/🐱/ по среднему состоянию. Полоски характеристик краснеют/желтеют.
* Тик каждые 30 секунд: до decay + сохранение + перерисовка панели, если
  открыт режим «Тамагочи» (setInterval на старте скрипта).
* Всё состояние уезжает в saveState (nexus_tamagotchi) и, как остальной
  прогресс, в облако комнаты через cloudPublishSoon после действий.

UI: плитка «Тамагочи» (fa-paw) в переключателе режимов (сетка стала
grid-cols-9), лобби #lobby-tama с панелью #tama-panel, которую целиком рисует
renderTamagotchi(): яйцо+кнопка покупки либо морда, уровень с полоской опыта,
четыре полоски характеристик и кнопки действий с ценой в монетах.

Классы взяты только из прекомпилированного tailwind.css (проверено: нет
text-6xl/7xl, sm:grid-cols-5, md:flex-row — вместо них text-5xl,
flex flex-wrap, flex-col lg:flex-row).

Менялись app.js и index.html — тег сборки nxmob226 -> nxmob227.

Проверка/применение:
    python3 tools/_b483_patch.py --check
    python3 tools/_b483_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob226'
TAG_NEW = 'nxmob227'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# --------------------------------------------------------------------------- #
# assets/app.js: состояние и сохранение питомца
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            windowBuys: JSON.parse(LS.getItem('nexus_window_buys') || '{}'),''',
              r'''            windowBuys: JSON.parse(LS.getItem('nexus_window_buys') || '{}'),
            tamagotchi: JSON.parse(LS.getItem('nexus_tamagotchi') || 'null') || null, // b483: питомец вкладки «Игры»'''))

PAIRS.append(('assets/app.js', 1,
              r'''                LS.setItem('nexus_window_buys', JSON.stringify(state.windowBuys || {})); // b277''',
              r'''                LS.setItem('nexus_window_buys', JSON.stringify(state.windowBuys || {})); // b277
                LS.setItem('nexus_tamagotchi', JSON.stringify(state.tamagotchi || null)); // b483'''))

# --------------------------------------------------------------------------- #
# assets/app.js: модуль тамагочи (перед setBattleMode)
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''        function setBattleMode(m) {''',
              r'''        // ============ b483: ТАМАГОЧИ — питомец на балансе игры ============
        // Новый режим вкладки «Игры». ВСЕ действия тратят монеты из общего
        // баланса (TAMA_COST); характеристики тают в реальном времени, включая
        // офлайн (кап 12 часов — неделя отсутствия не убивает питомца); при
        // среднем ниже 25 питомец болеет (доступно только лечение); за действия
        // капает опыт, на новом уровне питомец дарит случайную карту альбома.
        const TAMA_COST = { adopt: 100, feed: 15, play: 20, wash: 10, sleep: 5, heal: 40 };
        const TAMA_DECAY_PER_MIN = { hunger: 0.5, mood: 0.4, energy: 0.3, clean: 0.25 };
        const TAMA_OFFLINE_CAP_MIN = 12 * 60;
        const TAMA_ACTIONS = [
            { id: 'feed', label: 'Покормить', icon: '🍗', cost: TAMA_COST.feed, hint: '+сытость, немного пачкается' },
            { id: 'play', label: 'Поиграть', icon: '🎮', cost: TAMA_COST.play, hint: '+настроение, −энергия и −сытость' },
            { id: 'wash', label: 'Помыть', icon: '<i class="fa-solid fa-soap"></i>', cost: TAMA_COST.wash, hint: '+чистота' },
            { id: 'sleep', label: 'Уложить', icon: '<i class="fa-solid fa-moon"></i>', cost: TAMA_COST.sleep, hint: '+энергия' },
            { id: 'heal', label: 'Лечить', icon: '<i class="fa-solid fa-stethoscope"></i>', cost: TAMA_COST.heal, hint: 'снимает болезнь' },
        ];
        function tamaXpNeed(level) { return 40 + level * 20; }
        function tamaSpend(cost, what) {
            if (state.coins < cost) { showToast('Не хватает монет: ' + what + ' — ' + cost + ', у вас ' + state.coins, 'error'); return false; }
            state.coins -= cost;
            updateCoinDisplay();
            saveState();
            return true;
        }
        function tamaSync(now) {
            const t = state.tamagotchi;
            if (!t) return;
            const nowTs = now || Date.now();
            let mins = Math.max(0, (nowTs - (t.lastTs || nowTs)) / 60000);
            mins = Math.min(mins, TAMA_OFFLINE_CAP_MIN); // офлайн-тлен не убивает за неделю
            if (mins <= 0) return;
            t.hunger = Math.max(0, t.hunger - TAMA_DECAY_PER_MIN.hunger * mins);
            t.mood = Math.max(0, t.mood - TAMA_DECAY_PER_MIN.mood * mins);
            t.energy = Math.max(0, t.energy - TAMA_DECAY_PER_MIN.energy * mins);
            t.clean = Math.max(0, t.clean - TAMA_DECAY_PER_MIN.clean * mins);
            if (!t.sick && (t.hunger + t.mood + t.energy + t.clean) / 4 < 25) t.sick = true;
            t.lastTs = nowTs;
        }
        function tamaFace(t) {
            if (!t) return '🥚';
            if (t.sick) return '🤒';
            if (t.energy < 25) return '😴';
            const avg = (t.hunger + t.mood + t.energy + t.clean) / 4;
            if (avg >= 75) return '😺';
            if (avg >= 45) return '🐱';
            return '😿';
        }
        function tamaGift() { // подарок за уровень: случайная карта альбома
            try {
                const packs = state.packs.filter(p => state.cards.some(c => c.packId === p.id));
                if (!packs.length) return null;
                const pack = packs[Math.floor(Math.random() * packs.length)];
                const packCards = state.cards.filter(c => c.packId === pack.id);
                const card = rollCardFromPack(packCards, false, pack);
                if (!card) return null;
                state.collection[card.id] = (state.collection[card.id] || 0) + 1;
                return cardDisplayName(card);
            } catch (e) { return null; }
        }
        function tamaAdopt() {
            if (state.tamagotchi) { showToast('Питомец уже живёт у вас', 'error'); return; }
            if (!tamaSpend(TAMA_COST.adopt, 'купить яйцо')) return;
            state.tamagotchi = { name: 'Тоша', level: 1, xp: 0, hunger: 80, mood: 80, energy: 80, clean: 80, sick: false, lastTs: Date.now(), adoptedAt: Date.now() };
            saveState();
            showToast('🐣 Тоша вылупился! Действия тратят монеты, а за уровни питомец приносит карты альбома', 'success');
            renderTamagotchi();
        }
        function tamaAct(kind) {
            const t = state.tamagotchi;
            if (!t) { tamaAdopt(); return; }
            tamaSync();
            const act = TAMA_ACTIONS.find(a => a.id === kind);
            const cost = TAMA_COST[kind] || 0;
            if (t.sick && kind !== 'heal') { showToast('🤒 Тоша болен: сначала вылечите (' + TAMA_COST.heal + ' монет) — остальные действия недоступны', 'error'); renderTamagotchi(); return; }
            if (kind === 'heal' && !t.sick) { showToast('Тоша здоров — лечение не нужно', 'error'); return; }
            if (!tamaSpend(cost, (act ? act.label : kind).toLowerCase())) { renderTamagotchi(); return; }
            if (kind === 'feed') { t.hunger = Math.min(100, t.hunger + 35); t.clean = Math.max(0, t.clean - 4); }
            if (kind === 'play') { t.mood = Math.min(100, t.mood + 30); t.energy = Math.max(0, t.energy - 12); t.hunger = Math.max(0, t.hunger - 6); }
            if (kind === 'wash') { t.clean = Math.min(100, t.clean + 40); }
            if (kind === 'sleep') { t.energy = Math.min(100, t.energy + 35); }
            if (kind === 'heal') { t.sick = false; t.mood = Math.min(100, t.mood + 10); t.hunger = Math.max(t.hunger, 35); t.mood = Math.max(t.mood, 35); t.energy = Math.max(t.energy, 35); t.clean = Math.max(t.clean, 35); } // b483: лечение подтягивает тонус выше порога болезни, иначе питомец перезаболел бы через миллисекунду
            t.xp = (t.xp || 0) + 10;
            let gifted = null;
            while (t.xp >= tamaXpNeed(t.level)) { t.xp -= tamaXpNeed(t.level); t.level++; gifted = tamaGift(); }
            t.lastTs = Date.now();
            saveState();
            try { cloudPublishSoon(); } catch (e) {}
            renderTamagotchi();
            if (gifted) showToast('🎁 Уровень ' + t.level + '! Тоша принёс карту «' + gifted + '»', 'success');
        }
        function tamaBar(label, icon, val) {
            const col = val > 50 ? 'bg-emerald-500' : (val > 25 ? 'bg-amber-400' : 'bg-rose-500');
            return `<div class="min-w-0">
                <div class="flex justify-between text-[10px] text-slate-400 mb-0.5"><span>${icon} ${label}</span><b class="text-slate-200">${Math.round(val)}</b></div>
                <div class="h-2 rounded-full bg-slate-800 overflow-hidden"><div class="h-full ${col} rounded-full" style="width:${Math.max(0, Math.min(100, val))}%"></div></div>
            </div>`;
        }
        function renderTamagotchi() {
            const box = document.getElementById('tama-panel');
            if (!box) return;
            const t = state.tamagotchi;
            if (!t) {
                box.innerHTML = `<div class="text-center py-6 space-y-3">
                    <div class="text-5xl">🥚</div>
                    <p class="text-sm text-slate-300 font-bold">Пока никто не живёт</p>
                    <p class="text-[11px] text-slate-500 max-w-md mx-auto leading-snug">Купите яйцо за ${TAMA_COST.adopt} монет — питомец вылупится и будет расти. Каждое действие (покормить, поиграть, помыть, уложить, лечить) тратит монеты из баланса, а за новые уровни питомец приносит карты альбома.</p>
                    <button type="button" onclick="tamaAdopt()" class="px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold transition shadow-lg"><i class="fa-solid fa-egg mr-1.5"></i>Купить яйцо · <i class="fa-solid fa-coins mr-1"></i>${TAMA_COST.adopt}</button>
                </div>`;
                return;
            }
            tamaSync();
            const need = tamaXpNeed(t.level);
            const btns = TAMA_ACTIONS.map(a => {
                const off = (a.id === 'heal' && !t.sick);
                return `<button type="button" onclick="tamaAct('${a.id}')" title="${a.hint}" class="px-3 py-2 rounded-xl ${off ? 'bg-slate-900 text-slate-600 border border-slate-800' : 'bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200'} text-[11px] font-bold transition flex flex-col items-center gap-0.5">
                    <span class="text-base leading-none">${a.icon}</span><span>${a.label} · <i class="fa-solid fa-coins text-amber-300"></i>${a.cost}</span>
                </button>`;
            }).join('');
            box.innerHTML = `<div class="flex flex-col lg:flex-row gap-4 items-start">
                <div class="text-center lg:text-left shrink-0">
                    <div class="text-5xl leading-none">${tamaFace(t)}</div>
                    <p class="mt-2 text-sm font-black text-white">${t.name || 'Тоша'}${t.sick ? ' <span class="text-rose-300">· болен</span>' : ''}</p>
                    <p class="text-[10px] text-slate-400">уровень <b class="text-violet-300">${t.level}</b> · рост ${Math.round(t.xp || 0)}/${need}</p>
                    <div class="mt-1 h-2 w-32 mx-auto lg:mx-0 rounded-full bg-slate-800 overflow-hidden"><div class="h-full bg-violet-500 rounded-full" style="width:${Math.min(100, Math.round((t.xp || 0) / need * 100))}%"></div></div>
                </div>
                <div class="space-y-2.5 min-w-0 w-full">
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                        ${tamaBar('Сытость', '🍗', t.hunger)}
                        ${tamaBar('Настроение', '🎭', t.mood)}
                        ${tamaBar('Энергия', '⚡', t.energy)}
                        ${tamaBar('Чистота', '🫧', t.clean)}
                    </div>
                    <div class="flex flex-wrap gap-2 pt-1">${btns}</div>
                    <p class="text-[10px] text-slate-600 leading-snug">Характеристики тают со временем (офлайн — до 12 часов). Среднее ниже 25 — питомец заболевает, доступно только лечение. За уровень питомец приносит случайную карту альбома.</p>
                </div>
            </div>`;
        }
        // b483: тик 30 секунд: до-тление по таймеру + сохранение + перерисовка
        // панели, если режим «Тамагочи» сейчас открыт
        setInterval(function () {
            try {
                if (state.tamagotchi) { tamaSync(); saveState(); }
                const tab = document.getElementById('tab-battle');
                if (tab && !tab.classList.contains('hidden') && battleMode === 'tama') renderTamagotchi();
            } catch (e) {}
        }, 30000);

        function setBattleMode(m) {'''))

# --------------------------------------------------------------------------- #
# assets/app.js: setBattleMode знает режим tama
# --------------------------------------------------------------------------- #
PAIRS.append(('assets/app.js', 1,
              r'''            const ll = document.getElementById('lobby-lines');
            if (ll) ll.classList.toggle('hidden', m !== 'lines');''',
              r'''            const ll = document.getElementById('lobby-lines');
            if (ll) ll.classList.toggle('hidden', m !== 'lines');
            const lt = document.getElementById('lobby-tama'); // b483
            if (lt) lt.classList.toggle('hidden', m !== 'tama');'''))

PAIRS.append(('assets/app.js', 1,
              r'''            setModeBtn('mode-lines-btn', m === 'lines', 'lq-on');''',
              r'''            setModeBtn('mode-lines-btn', m === 'lines', 'lq-on');
            setModeBtn('mode-tama-btn', m === 'tama', 'lq-on'); // b483'''))

PAIRS.append(('assets/app.js', 1,
              r'''            if (m === 'miner') renderMiner();''',
              r'''            if (m === 'miner') renderMiner();
            if (m === 'tama') renderTamagotchi(); // b483'''))

# --------------------------------------------------------------------------- #
# index.html: плитка режима и лобби
# --------------------------------------------------------------------------- #
PAIRS.append(('index.html', 1,
              r'''                <div class="grid grid-cols-8 gap-1 sm:gap-2 w-full py-0.5">''',
              r'''                <div class="grid grid-cols-9 gap-1 sm:gap-2 w-full py-0.5"><!-- b483: девятая плитка — Тамагочи -->'''))

PAIRS.append(('index.html', 1,
              r'''<button onclick="setBattleMode('wheel')" id="mode-wheel-btn" class="w-full flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-xl text-[13px] sm:text-[15px] lg:text-[13px] font-bold transition whitespace-nowrap overflow-hidden min-w-0 lg:flex-row lg:gap-1.5 lg:px-2 bg-slate-800 text-slate-300 border border-slate-700"><i class="fa-solid fa-dharmachakra mr-0 lg:mr-1.5"></i><span class="block lg:inline w-full lg:w-auto text-center lg:text-left text-[8px] sm:text-[9px] lg:text-xs font-bold leading-none truncate">Колесо</span></button>''',
              r'''<button onclick="setBattleMode('wheel')" id="mode-wheel-btn" class="w-full flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-xl text-[13px] sm:text-[15px] lg:text-[13px] font-bold transition whitespace-nowrap overflow-hidden min-w-0 lg:flex-row lg:gap-1.5 lg:px-2 bg-slate-800 text-slate-300 border border-slate-700"><i class="fa-solid fa-dharmachakra mr-0 lg:mr-1.5"></i><span class="block lg:inline w-full lg:w-auto text-center lg:text-left text-[8px] sm:text-[9px] lg:text-xs font-bold leading-none truncate">Колесо</span></button>
                <button onclick="setBattleMode('tama')" id="mode-tama-btn" class="w-full flex flex-col items-center justify-center gap-1 px-1 py-2 rounded-xl text-[13px] sm:text-[15px] lg:text-[13px] font-bold transition whitespace-nowrap overflow-hidden min-w-0 lg:flex-row lg:gap-1.5 lg:px-2 bg-slate-800 text-slate-300 border border-slate-700" title="Тамагочи: питомец тратит ваш баланс на еду, игры и уход, а за уровни дарит карты"><i class="fa-solid fa-paw mr-0 lg:mr-1.5"></i><span class="block lg:inline w-full lg:w-auto text-center lg:text-left text-[8px] sm:text-[9px] lg:text-xs font-bold leading-none truncate">Тамагочи</span></button>'''))

PAIRS.append(('index.html', 1,
              r'''            <div id="battle-lobby" class="space-y-6">''',
              r'''            <div id="battle-lobby" class="space-y-6">
                <!-- b483: лобби режима «Тамагочи» — содержимое рисует renderTamagotchi() -->
                <div id="lobby-tama" class="space-y-6 hidden">
                    <div class="bg-gradient-to-r from-slate-900 to-slate-900/60 p-4 sm:p-6 rounded-2xl border border-slate-800">
                        <div class="flex flex-wrap items-start justify-between gap-3">
                            <div class="min-w-0">
                                <h2 class="text-2xl font-black text-white tracking-tight"><i class="fa-solid fa-paw text-amber-300 mr-2"></i>Тамагочи</h2>
                                <p class="text-sm text-slate-400 mt-1">Питомец на балансе игры: каждое действие тратит монеты, питомец растёт и приносит карты альбома.</p>
                            </div>
                        </div>
                        <div id="tama-panel" class="mt-4"></div>
                    </div>
                </div>'''))


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
        print('b483: якоря (%d) и тег %s на месте, можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b483: тамагочи в «Играх» — все действия тратят баланс; тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
