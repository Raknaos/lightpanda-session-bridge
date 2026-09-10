#!/usr/bin/env bash
# Verification live du relais supervise (aucune valeur de secret n'est affichee).
set -u
export MSYS_NO_PATHCONV=1
TOK=$(cat "$HOME/.config/lightpanda-bridge/secret")
echo "=== 1. sante ==="
curl -s -m 5 http://127.0.0.1:8765/health; echo
echo "=== 2. tache supervisee ==="
schtasks /query /tn LightpandaRelayDaemon /fo LIST 2>&1 | grep -iE "Statut|Status|TaskName" | head -3
echo "=== 3. proprietaire du port ==="
PID=$(netstat -ano | grep "127.0.0.1:8765" | grep -i listen | awk '{print $5}' | head -1)
echo "PID=$PID"
wmic process where "ProcessId=$PID" get ExecutablePath,CommandLine /format:list 2>/dev/null | grep -iE "ExecutablePath|CommandLine" | head -4
echo "=== 4. sessions connues (metadonnees seules) ==="
curl -s -m 5 -H "X-Bridge-Token: $TOK" http://127.0.0.1:8765/v1/sessions; echo
echo "=== 5. etat persistant sur disque ==="
if [ -f "$HOME/.config/lightpanda-bridge/session.json" ]; then
  echo "session.json present"
  python - <<'PY'
import json, os
p = os.path.join(os.path.expanduser("~"), ".config", "lightpanda-bridge", "session.json")
d = json.load(open(p, encoding="utf-8"))
print("origin:", d["origin"], "| cookies:", [c["name"] for c in d["cookies"]],
      "| storage keys:", len(d.get("storage", {})))
PY
else
  echo "session.json absent (aucune synchro depuis le redemarrage)"
fi
echo "=== 6. refus d'un appelant non authentifie ==="
curl -s -m 5 -o /dev/null -w "sans token: HTTP %{http_code}\n" -X POST http://127.0.0.1:8765/v1/sessions/clear
curl -s -m 5 -o /dev/null -w "origine web: HTTP %{http_code}\n" -H "Origin: https://evil.example" -H "X-Bridge-Token: $TOK" http://127.0.0.1:8765/v1/sessions
echo "=== 7. banniere serveur ==="
curl -s -m 5 -D - -o /dev/null http://127.0.0.1:8765/health | grep -i "^server:"