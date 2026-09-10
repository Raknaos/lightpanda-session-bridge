import json, io, os, sys

UD = os.path.expanduser(r'~/AppData/Local/Perplexity/Comet/User Data')
EID = 'fcigkjkchglchhohedljlenopbkgnino'

for prof in ('Default', 'Profile 1', 'Profile 2', 'Profile 3'):
    for name in ('Preferences', 'Secure Preferences'):
        p = os.path.join(UD, prof, name)
        if not os.path.isfile(p):
            continue
        raw = io.open(p, encoding='utf-8', errors='ignore').read()
        n = raw.count(EID)
        print(f'{prof}/{name}: {n} occurrence(s) de l id, {len(raw)} octets')
        if n == 0:
            continue
        try:
            d = json.loads(raw)
        except Exception as e:
            print('  json KO:', e)
            continue
        s = d.get('extensions', {}).get('settings', {})
        print('  nb extensions enregistrees:', len(s))
        for k, v in s.items():
            if k.startswith(EID):
                m = v.get('manifest', {})
                print('  -->', k)
                print('      path   =', v.get('path'))
                print('      state  =', v.get('state'), '| location =', v.get('location'))
                print('      version=', m.get('version'), '| host_perms =', m.get('host_permissions'))
                print('      disable_reasons =', v.get('disable_reasons'))
