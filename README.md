# Lightpanda Session Bridge

Application locale dédiée au transfert explicite d'une session de site vers Lightpanda.

## Résultat du test Neo

Neo (`4ier/neo`, version 2.1.0) se connecte à Lightpanda, mais son cycle de vie n'est pas suffisant pour ce cas :

- son WebSocket persistant empêche certaines commandes mono-shot de se terminer ;
- Lightpanda renvoie un `sessionId` après `Target.attachToTarget`, que Neo ne propage pas à toutes les commandes ;
- les cibles Lightpanda créées sont liées à la connexion CDP qui les possède et disparaissent quand cette connexion est fermée ;
- son import de cookies n'impose pas de domaine cible côté CLI.

Neo reste conservé dans `neo-upstream/` comme référence et banc d'essai. Le relais de ce projet implémente le protocole CDP nécessaire directement, avec une connexion persistante et une vérification de lecture après import.

## Modèle de sécurité

- L'utilisateur se connecte normalement dans Chromium.
- L'extension ne lit les cookies qu'après confirmation explicite du domaine affiché.
- Le relais refuse HTTP, localhost, IP privées et fournisseurs d'identité.
- Google, Microsoft, Apple, Auth0 et GitHub ne peuvent pas être des cibles de transfert.
- Les cookies sont limités au domaine de l'origine confirmée ou à ses domaines parents.
- Le relais écoute uniquement sur `127.0.0.1`.
- Les mots de passe, codes OAuth, clés API, tokens et valeurs de cookies ne sont jamais écrits dans les logs ou les fichiers du projet.
- Le transfert ne contourne ni MFA, ni CAPTCHA, ni validation de sécurité.

## Utilisation Windows

1. Démarrer Lightpanda avec un profil de cookies isolé :

```powershell
.\scripts\start-lightpanda.ps1
```

2. Démarrer le relais :

```powershell
.\scripts\start-relay.ps1
```

3. Dans un profil Chromium dédié, ouvrir `chrome://extensions`, activer le mode développeur et charger `extension/` comme extension non empaquetée.

4. Se connecter au service cible dans Chromium. Pour A6API, terminer la connexion Google puis revenir sur `https://a6api.com/console/log`.

5. Ouvrir l'extension, vérifier l'origine affichée, cocher la confirmation et lancer le transfert.

Le relais ne confirme l'opération qu'après une lecture CDP vérifiant la présence des cookies importés dans Lightpanda.

## Tests

```bash
python -m unittest discover -s tests -v
python relay/server.py --self-test
python -m py_compile relay/server.py
```

Le test d'intégration utilisé pendant le développement a importé un cookie fictif sur `example.com` via l'API HTTP puis a reçu `200` et `cookie_count: 1`.

## Limitation Lightpanda

Lightpanda n'est pas Chromium. Certains services lient la session au navigateur, à l'appareil, au stockage local ou à un service worker. Un transfert de cookies peut donc être accepté techniquement mais refusé ensuite par le service cible. Pour A6API, la première validation doit être faite avec un transfert explicite de `a6api.com`, jamais avec les cookies de Google.

## Licence

MIT
