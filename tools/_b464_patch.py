#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b464: переходный режим Студии — пока сервер не задеплоен, владелец не остаётся за дверью.

Зачем
─────
В b463 проверка пароля Студии переехала на сервер: клиент отправляет пароль,
сервер сверяет его со своим PBKDF2-хэшем и выдаёт админ-токен. Это правильно,
но дало побочный эффект: если адрес API ещё не указан (воркер не задеплоен),
`submitStudioPass()` отвечал «Сервер не подключён» и НЕ открывал Студию вовсе.
Владелец терял доступ к редактору контента (паки, карты, сторис, расписание)
до конца деплоя.

Что сделано
───────────
Добавлен переходный режим: если API не настроен, Студия открывается как
РЕДАКТОР КОНТЕНТА, а не как админка. Безопасность при этом не страдает:

  • сравнения пароля в клиентском коде НЕ появляется — проверять нечем и не с
    чем (хэша пароля в клиенте больше нет вовсе, b463 его удалил);
  • все действия админки (обнулить/заблокировать/поставить банк/выдать джекпот/
    настройки джекпота/каталог) идут через nxAdminAct() и требуют серверный
    админ-токен. Без токена они возвращают admin_required и не выполняются —
    ни здесь, ни на сервере. То есть денег и банка переходный режим не даёт;
  • деньги в этом режиме считаются локально, как и до b463 (сервера нет —
    считать некому), а после подключения сервера баланс и банк становятся
    серверными, и локальные числа перестают что-либо решать.

Плюс понятная подпись в панели «Джекпот» и тост: что недоступно и что сделать
(задеплоить server/ и указать адрес API в разделе «Облако»).

app.js менялся — тег сборки nxmob186 -> nxmob187 (index.html, sw.js,
tools/build.py).

Проверка/применение:
    python3 tools/_b464_patch.py --check
    python3 tools/_b464_patch.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_OLD = 'nxmob186'
TAG_NEW = 'nxmob187'
TAG_FILES = ['index.html', 'sw.js', 'tools/build.py']

PAIRS = []

# 1) переходный режим входа в Студию
PAIRS.append(('assets/app.js', '''            const ref = CLOUD.remoteAuth || cloudLocalAuth();
            if (!nxApiConfigured()) {
                showErr('Сервер не подключён: укажите адрес API в разделе «Облако» — вход в Студию проверяет сервер');
                return;
            }''',
              '''            const ref = CLOUD.remoteAuth || cloudLocalAuth();
            if (!nxApiConfigured()) {
                // ============ b464: ПЕРЕХОДНЫЙ РЕЖИМ (сервер ещё не задеплоен) ======
                // Проверять пароль НЕЧЕМ и не с чем: хэша пароля в клиентском коде
                // больше нет (b463 его удалил), а сервера нет. Поэтому:
                //   • никакого сравнения пароля здесь не появляется;
                //   • Студия открывается как РЕДАКТОР КОНТЕНТА (паки, карты, сторис,
                //     расписание) — ровно то, что и раньше было доступно владельцу;
                //   • админка НЕ работает: каждое действие (обнулить/заблокировать/
                //     поставить банк/выдать джекпот/настройки/каталог) идёт через
                //     nxAdminAct() и требует серверный админ-токен. Без токена —
                //     admin_required, ни здесь, ни на сервере действие не выполняется.
                showErr('Сервер не подключён: баланс, банк и джекпот недоступны. Студия открыта как редактор контента');
                studioUnlocked = true;
                cloudRole = 'owner';
                setTimeout(() => {
                    try { closeStudioPassModal(); } catch (e2) {}
                    try { switchTab('studio'); } catch (e2) {}
                    try { nxStudioNoServerBanner(); } catch (e2) {}
                    try {
                        showToast('⚠️ Сервер не подключён: доступен только контент Студии. ' +
                            'Балансы, банк и джекпот — после деплоя server/ (см. server/README.md)', 'info');
                    } catch (e2) {}
                }, 900);
                return;
            }'''))

# 2) подпись в панели «Джекпот» о том, что сервер не подключён
PAIRS.append(('assets/app.js', '''        function nxOpenStudioPassFromAdmin() {''',
              '''        // b464: понятная подпись, когда сервер ещё не подключён
        function nxStudioNoServerBanner() {
            const txt = '⚠️ Сервер не подключён — банк, выдачи и настройки джекпота недоступны. ' +
                'Задеплойте server/ (server/README.md) и укажите адрес API в разделе «Облако».';
            try {
                const note = document.getElementById('jpc-note');
                if (note) note.textContent = txt;
            } catch (e) {}
            try {
                const box = document.getElementById('jpc-users');
                if (box && !box.textContent.trim()) box.innerHTML = '<p class="text-[11px] text-amber-300/90">' + txt + '</p>';
            } catch (e) {}
        }
        function nxOpenStudioPassFromAdmin() {'''))

# 3) без сервера панель «Джекпот» не пытается тянуть реестр с сервера
PAIRS.append(('assets/app.js', '''        function jpcRefresh() {
            // b463: данные игроков и банка тянем с сервера
            try { if (nxServerMode() || nxAdminHasToken()) nxSrvPullUsers(); } catch (e) {}''',
              '''        function jpcRefresh() {
            // b463: данные игроков и банка тянем с сервера
            // b464: без подключённого API показываем, чего не хватает, а не молчим
            try {
                if (nxServerMode() || nxAdminHasToken()) nxSrvPullUsers();
                else if (!nxApiConfigured()) { nxStudioNoServerBanner(); showToast('⚠️ Сервер не подключён — реестр игроков и банк недоступны', 'info'); }
            } catch (e) {}'''))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, txt):
    with io.open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        f.write(txt)


def main():
    files = {}
    problems = []
    for rel, old, new in PAIRS:
        txt = files.get(rel) if rel in files else read(rel)
        o, n = old.strip('\n'), new.strip('\n')
        c = txt.count(o)
        if c != 1:
            problems.append('%s: якорь встретился %d раз: %s...' % (rel, c, o[:70].replace('\n', ' / ')))
            continue
        files[rel] = txt.replace(o, n, 1)
    for rel in TAG_FILES:
        txt = files.get(rel) if rel in files else read(rel)
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
        print('b464: все %d якорей найдены ровно по разу, тег %s на месте — можно применять' % (len(PAIRS), TAG_OLD))
        return 0
    for rel, txt in files.items():
        write(rel, txt)
    print('b464: переходный режим Студии без сервера (контент — да, админка — нет); тег %s -> %s' % (TAG_OLD, TAG_NEW))
    return 0


if __name__ == '__main__':
    sys.exit(main())
