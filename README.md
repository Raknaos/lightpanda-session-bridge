# Lightpanda Session Bridge

Pont sécurisé permettant de synchroniser les sessions web authentifiées (cookies et stockage local) depuis un navigateur Chromium standard (Chrome / Comet / Hermes) vers un moteur headless **Lightpanda** fonctionnant sous WSL2 via Chrome DevTools Protocol (CDP).

---

## 🔒 Principes d'architecture & sécurité

- **Zéro fuite de mots de passe / tokens d'identité :** Aucun mot de passe, code MFA, token OAuth ou secret Google/IdP n'est transmis ni conservé.
- **Portée stricte par origine HTTPS :** Seules les sessions de sites publics validés (ex: `https://a6api.com`) sont autorisées. Tout domaine d'authentification tiers (`accounts.google.com`, `auth0`, etc.) ou IP privée/locale (`localhost`, `127.0.0.1`, RFC1918) est systématiquement rejeté par le relais.
- **Filtrage des cookies :** Les attributs internes d'extension (`storeId`, etc.) sont purgés. Les domaines de cookies doivent correspondre strictement à l'origine cible.
- **Support localStorage sécurisé :** Injection isolée dans le contexte du document Lightpanda.

---

## 📁 Structure du projet

- **`extension/`** : Extension Chrome Manifest V3 avec interface sombre moderne, auto-détection de l'état du relais local, validation explicite et transfert 1-clic.
- **`relay/server.py`** : Relais HTTP local (boucle locale `127.0.0.1:8765`) assurant la validation, la connexion CDP persistante vers Lightpanda (`127.0.0.1:9222`) et l'injection ciblée.
- **`sync_session.py`** : Outil CLI d'automatisation direct qui synchronise automatiquement l'onglet actif sans avoir à cliquer sur l'extension si souhaité.
- **`lightpanda_client.py`** : SDK Python pour piloter Lightpanda via CDP et exécuter des requêtes/évaluations sur la session injectée.
- **`tests/test_security.py`** : Suite de tests unitaires vérifiant le rejet des IdP, des URL invalides et des cookies mal formés.

---

## 🚀 Démarrage rapide

### 1. Lancer Lightpanda (WSL2)
```powershell
./scripts/start-lightpanda.ps1
```
Vérifier l'écoute CDP sur `http://127.0.0.1:9222/json/version`.

### 2. Lancer le relais local
```powershell
python relay/server.py --port 8765
```
Ou en tâche de fond :
```powershell
./scripts/start-relay.ps1
```

### 3. Synchronisation d'une session

**Option A - Via l'extension Chrome :**
1. Charger le dossier `extension/` dans `chrome://extensions` (Mode développeur -> Charger le dossier non empaqueté).
2. Se connecter normalement sur le site cible (ex: `https://a6api.com`) avec son compte Google.
3. Cliquer sur l'icône Lightpanda Bridge, cocher l'autorisation et valider.

**Option B - Via le script direct `sync_session.py` :**
```bash
python sync_session.py
```

### 4. Utiliser Lightpanda avec la session
```python
from lightpanda_client import LightpandaClient

client = LightpandaClient()
client.connect()
client.attach_or_create("https://a6api.com/console/log")
# Exécution de requêtes authentifiées...
```

---

## 🧪 Tests de sécurité
```bash
python -m unittest discover -s tests -v
python relay/server.py --self-test
```
