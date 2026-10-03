## [0.7.22] - « à jour » et « la branche a avancé » ne sont pas la même nouvelle

`shipped_tree: "same"` couvre deux situations distinctes : `main` a avancé sur
des commits hors `extension/` (la phrase est vraie), ou l'arbre déployé EST la
pointe de `main` (rien n'a bougé). Le popup imposait la même phrase aux deux, et
disait donc « la branche a avancé » à un utilisateur entièrement à jour.
Séparation faite sur une mesure que le popup possède déjà (`current_commit`
contre `latest_commit`) : à la pointe -> « À jour · v0.7.21 » ; sinon la phrase
existante, inchangée. Repli sur la puce sans version quand la version est absente,
car `updateUpToDate` l'interpole.

`tests/node/test_update_card_truth.js` : 18 -> **36** tests, les deux phrases
sont comparées par **égalité exacte** à la chaîne du dictionnaire.
`scripts/proof_red_update_tip.py` : **3 sabotages, 3 rouges nommés, 0 invalide**,
`popup.js` restauré à l'octet. Check `the popup tells 'at the tip of main' apart
from 'the branch moved on'` enregistré dans `LOCAL`, influence prouvé (compte
truqué -> `NOT READY`).

Deux erreurs de harnais valent plus que le correctif : `!/avance|avanz|moved/i`
est resté **vert sur le code non corrigé** (le français dit « avancé », et aucune
des dix langues n'écrit « advance ») ; et deux sabotages ont rendu une sortie
**identique**, ce qui a révélé un modèle du code faux, pas un test faux.

## [0.7.21] - le rapport de diagnostic dit POURQUOI la pastille est silencieuse

Il portait `update_available = False` et rien d'autre. C'est la page que
l'utilisateur colle dans un bug : impossible d'y distinguer « rien de nouveau »
de « une mise a jour qui traine ». Le rapport publie desormais l'**etat mesure**
(`update_state` : `same` / `differs` / `unknown`) et `update_note`, la raison.

**La fuite que l ajout a introduite, et que seul le harnais a trouvee.**
`update_note` est ecrit par le RELAIS : c'est du texte etranger. Il vivait dans
un dict que ce module construit - donc jamais scrubbe, parce qu'une donnee
construite ici est trusted par construction. Une note lisant
`Authorization: Bearer ghp_A1...Q7r8` exportait **12 caracteres d'un jeton**
dans un rapport fait pour etre colle publiquement. La note passe desormais par
le scrubber ; et le cas inverse est fige par un test, parce qu'un scrubber trop
large est un defect de meme gravite qu'une fuite : un sha de git doit y
survivre intact.

**Un check du gate etait vert sans mesurer quoi que ce soit.** Trois checks
lisaient la sortie des suites Node avec `endswith("passed")`, alors qu'elles
impriment `18 passed, 0 failed` - une ligne qui finit par « failed ». Le motif
ne matchait rien, la valeur par defaut `?` etait renvoyee, et le verdict
affichait `ok ... ?` : vert et aveugle. Meme famille que le point 13, un cran
plus bas - la-bas le check ne s'executait pas, ici il s'executait entierement et
sa mesure etait jetee. La mesure est desormais cherchee partout dans la ligne,
et une mesure absente est un FAIL plutot qu'un defaut silencieux. Prouve
influent : harnais muet -> `NOT READY`.

Nouveau `scripts/proof_red_update_report.py` (4 sabotages, 4 rouges nommes,
0 invalide). `tests/test_diagnostics.py` passe a 21 verts.

**Le cas le plus frequent n'avait AUCUNE branche.** Apres la correction
ci-dessus, le relais vivant respondeit encore `update_state: None`. La chaine
`if / elif` de `check_update` n'a pas de bras pour `head == current` - l'arbre
deploie EST la tete de `main`, le cas de presque tout utilisateur a jour -: il
passe droit au `return`, et les deux faits n'existaient qu'A l'interieur des
bras conditionnels. Deux correctifs : un bras dedie, dont la note ne dit
jamais "byte-identical" puisque rien n'a ete hache ; et l'invariant
structurel, `shipped_tree`/`note` initialises dans le dict de depart
(`"unknown"` / `None`) puis rafines. Avant, les cas « ni release ni main » et
« erreur reseau » renvoyaient une cle ABSENTE ; apres, `unknown`. Mesure sur le
relais vivant : `update_state = same`, aucune cle absente. 3 tests, 3
sabotages rouges nommes - dont un qui retire la garde du bras et prouve qu'un
arbre reellement different continue d'offrir sa mise a jour.

**Changelog repare.** Le fichier portait l'historique **deux fois** (74 entrees
pour 37 versions, 34 identiques au caractere pres) et l'entree 0.7.20 etait
collee sans saut de ligne au milieu d'une ligne 0.3.3
la ligne 0.3.3 terminait par un `).` suivi, sans retour a la ligne, du titre `## [0.7.20]` - et le paragraphe suivant y etait repete deux
fois. Aucun check ne le voyait : `versions_agree` ne cherche que le numero de
version, present dans les deux moities. Deduplique, collage coupe, paragraphe
unique conserve.

## [0.7.20] - le popup dit POURQUOI il n'y a rien a installer

Quand le relais mesure que les octets publies sont identiques, la pastille
affichait `A jour` suivi de `commit 34827e4`. C'est vrai et inutile: la branche
avance en permanence sur des commits de docs, donc l'utilisateur ne peut pas
distinguer « rien de neuf pour toi » de « un changement de code t'attend ».

Le popup traduit maintenant l'**etat mesure** (`shipped_tree: 'same'`), jamais la
note du relais - celle-ci porte un sha et de l'anglais, fait pour un journal et pas
pour un panneau en dix langues. Le commit reste dispo en infobulle.

Mesure avant: `meta = "commit 34827e4"` avec `shipped_tree = "same"`.

Nouveau `tests/node/test_update_card_truth.js` (18 verts) Cable en check LOCAL,
verifie influent: le sabotage du popup fait passer le gate de READY a NOT READY.
Il couvre aussi le cas inverse et l'absence de provenance, pour qu un harnais
qui ne rend rien echoue sur une sortie deja correcte.

Trois sabotages rouges, chacun nommant son propre defaut.

**Le relais mentait sur le meme point** (trouve en interrogeant le relais vivant
apres publication): `shipped_tree`, `shipped_tree_sha` et `local_tree_sha` valaient
tous `None`, et la note disait quand meme « the deployed tree is byte-identical ».
Le chemin rapide reutilisait le texte du chemin lent, ou le hachage avait eu lieu.
Corrige: chemin rapide -> `shipped_tree: "unknown"` et une note qui ne pretend rien
mesurer; `shipped_tree` desormais publie sur les DEUX chemins, puisque c'est lui que
le popup interroge. Un test preexistant pinnait l'ancien mensonge - migre vers le
contrat mesure. 2 nouveaux tests, 2 sabotages rouges. 11/11 nommes, 0 invalide.


**Preuve visuelle** sur l'extension reelle (compositeur, pas un DOM snapshot):
avec un commit anterieur installe et `main` ayant avance, le relais renvoie
`shipped_tree: "same"` et le popup affiche

    A jour
    Identique a la release publiee - la branche a avance   (infobulle: commit cb4bdf5)

Piège de mesure: un sha factice tronque a 33 caracteres au lieu de 40 n'est pas
reconnu comme un sha, le relais prend la branche « sans provenance » et renvoie
`shipped_tree: None` - la feature paraissait morte alors que la sonde etait
fausse. Point 54 du skill. Deux lessons de
harnais au skill (points 52/53): `vm.runInContext` avec le SOURCE d une fonction
ne fait que la DEFINIR - il faut l'appeler, sinon tous les champs restent vides
et le harnais accuse l'accesseur; et un test qui n'exerce que le nouveau
comportement laisse passer un harnais casse.

### le meme defaut survivait sans commit enregistre

Une installation manuelle n'a pas de commit, et cette branche ne comparait que les
versions. Mesure : version 0.7.19, sans commit, release 0.7.19 ->
`update_available: True, from 0.7.19 -> to 0.7.19`, c'est-a-dire la pastille
proposant de reinstaller la version identique a chaque verification. La branche
compare maintenant l'arbre local a celui du **tag**.

### et le premier correctif produisait l'inverse du defaut

Il sautait aussi la branche qui OFFRE l'installation : un arbre reellement
different repondait `update_available: False` - une mise a jour manquee derriere
un "a jour". Les deux sens sont desormais mesures dans la meme sonde et figes
par des tests.
## [0.7.19] - le canal de mise a jour compare les OCTETS, pas les COMMITS (et plus: la branche sans provenance non plus)

`check_update` decidait "installe ceci" en comparant des **commits**. Or le commit
enregistre a l'installation est la pointe du dernier `fetch` - regulierement un commit
qui n'a touche que `scripts/` ou `docs/`. Mesure sur 0.7.18 : installe `045eac3`,
dernier commit touchant `extension/` `37e958d`, et les deux portent le meme arbre
`c1090d37`. Les octets deposes etaient identiques, donc la pastille proposait une
mise a jour que l'utilisateur ne pouvait jamais vider - chaque installation
enregistrait a nouveau un commit non livre.

Desormais, en plus du filtre par sous-arbre, l'arbre **depose** est compare a
l'arbre **distant** :

- le local utilise le schema de **blob git** (`sha1("blob <len>\0" + octets)`),
  parce que c'est ce que renvoie l'API ; un sha256 nu comparait deux alphabets
  differents et signalait une difference sur les 14 fichiers livres, identiques
  octet pour octet ;
- les deux cotes sont cles par le meme chemin relatif au depot (`extension/popup.js`) ;
- `.build-info.json` est exclu : ecrit par l'installeur, non suivi, different sur
  chaque machine - l'inclure rend chaque arbre unique et la comparaison vide de sens.

Trois pieges de harnais rencontres en route, tous consignes : un sabotage qui
supprime l'argument de formatage leve `TypeError` au lieu de produire l'echec ; les
mots-cles `expect` doivent venir du message reellement affiche, `unittest` tronquant
une paire d'hex a la largeur de la fenetre ; et les callables remplaces doivent etre
sauvegardes dans `setUp`, pas dans le helper, sinon les tests qui ne l'appellent pas
lisent une constante residuelle et la faute tombe sur le produit.

Prouve par `scripts/proof_red_update_channel.py` : **5 sabotages, 5 rouges nommes**.

### le meme defaut survivait sans commit enregistre

Une installation manuelle n'a pas de commit, et cette branche ne comparait que les
versions. Mesure : version 0.7.19, sans commit, release 0.7.19 ->
`update_available: True, from 0.7.19 -> to 0.7.19`, c'est-a-dire la pastille
proposant de reinstaller la version identique a chaque verification. La branche
compare maintenant l'arbre local a celui du **tag**.

### et le premier correctif produisait l'inverse du defaut

Il sautait aussi la branche qui OFFRE l'installation : un arbre reellement
different repondait `update_available: False` - une mise a jour manquee derriere
un "a jour". Les deux sens sont desormais mesures dans la meme sonde et figes
par des tests.

## [0.7.18] - la chaine d'expiration de session, reellement cablee

Une session, importee depuis un cookie Chrome, n'affichait jamais son expiration :
`list_sessions()` calculait `expired`, mais la popup ne recevait jamais la date. La chaine
etait rompue en quatre points, tous couverts par des tests desormais :

1. `cookie_for_cdp()` rejettait `expires_hint` — la cle etait supprimee a l'entree du
   relais, donc `expires` revenait toujours a `None`. 
2. `item["expires_hint"]` n'etait ecrit que si l'echeance etait **future** — un cookie
   expire depuis une heure perdait son nombre, et `expired` ne pouvait jamais devenir vrai. 
3. La popup n'envoyait jamais `expires_hint` : elle envoyait `cookies`, qui porte
   `expirationDate`, laisse a l'ecart avant d'atteindre le relais. 
4. L'etat `expired` et le mot `cookies` etaient des litteraux anglais dans une popup a
   dix langues. 

Le compte a rebours etait faux dans les deux sens : `Math.floor` sous-estimait (3 h
lues "~2 h" parce que quelques millisecondes separaient l'horloge du test de celle du
produit), et l'arrondi surestimerait des le correctif de ce point (40 min lues "~1 h"). 
Regle appliquee : **les jours arrondissent au plafond, les heures a la tranche, et sous
une heure on compte en minutes** — un compte a rebours qui s'ecoule ne doit jamais
promettre plus de temps qu'il n'en reste. Un test a frontiere exacte (3 h 00) est
instable de quelques millisecondes et a ete remplace par des valeurs avec marge plus
une assertion de DIRECTION (3 h 35 doit lire "~3 h", pas "~4 h"). 

Prouve par `scripts/proof_red_session_expiry.py` : **8 sabotages, 8 rouges nommes**. 

Trois defauts de harnais trouves en chemin, qui rendaient la preuve invalide sans la
faire echouer :

- Le relais appartient a la tache `LightpandaRelayDaemon`, pas `LightpandaBridgeRelay` —
  le harnais redemarrant la mauvaise tache mesurait le code d'avant, pour toujours. 
- Arreter seulement le PREMIER processus laisse le survivant tenir le port, et le neuf
  sort en 0 sur "address already in use" : le sabotage ne tournait jamais. 
- Chercher la chaine "Failed to import test module" dans la sortie attrapait la
  docstring d'un test, et transformait un vrai rouge en faux `HARNESS`. 

Et une piege destructive : la copie "pristine" du harnais n'etait prise qu'a la
premiere execution. Apres un correctif ulterieur, la restauration remit le fichier
**avant** le correctif — l'assertion du harnais a echoue en detruisant le travail qu'elle
devait proteger. Le snapshot est desormais pris a chaque sabotage. 

La suite elle-meme a ete reprise apres que la CI l'a refutee - deux fois, et
les deux fois elle avait raison :

- Elle lisait le secret de l'operateur et postait vers le relais EN SERVICE sur
  8765 : `FileNotFoundError` sur le runner, cinq erreurs dont aucune ne parlait
  d'expiration. Elle sert maintenant le vrai `Handler` sur un port ephemere et
  possede son jeton.
- La route d'import exige un **Lightpanda vivant** (`_ensure_connection`,
  `_apply_session`, verification par `Network.getCookies`) : sur le runner sans
  navigateur elle repondait 400 "Connection refused". Le **transport** est sature,
  jamais le code sous test - la derivation de `cookie_for_cdp`, le garde-fou `> 0`
  et `list_sessions()` tournent pour de vrai.

Et le harnais de mesurePaint etait, lui aussi, incapable de voir la feature :
la ligne des sessions est livree **repliee**, donc la meta d'expiration n'etait
jamais peinte. Il clique desormais le vrai controle avant de capturer.

**Verifie sur l'extension installee 0.7.18**, par le compositeur, sur la vraie
origine : la ligne affiche `1 cookie · expirée`. Chaine complete, en francais,
aucun litteral `cookies`/`expired`, aucune valeur de cookie lue.

Gate : 34 checks (18 locaux + 16 live), 240 tests, CI verte sur `d11f3d2`.

## [0.7.17] - retracting 0.7.16: the wrong-language frame was never painted

v0.7.16 claimed the popup flashed French to English users. It did not. The claim
came from `Emulation.setScriptExecutionDisabled`, which proves the pre-translation
DOM exists - not that a frame reached the screen. `popup.js` is a parser-blocking
classic script at line 701 of a 704-line document, so Chrome holds the first paint
until it has run.

`Page.startScreencast` - the compositor, the only authority on what was shown -
recorded the real installed popup on `chrome-extension://<id>`: the FIRST frame is
already fully French (`FR`, "Copier le diagnostic", v0.7.16, relay online). No
flash, ever.

The v0.7.16 gate check and all four harnesses that produced the finding are
removed. `scripts/measure_real_popup_screencast.py` is kept: it measures the
installed product on its real origin, and reading the frames is the only way to
tell a language change from a state change (30% of pixels differed between two
frames that were both French).

The HTML change itself - `Copier le diagnostic` -> `Copy diagnostic` - is kept. It
is the default language, so the literal now matches what the untranslated panel
would say if a browser ever did paint it early.

## [0.7.16] - a popup painted one wrong-language frame before any script ran

`#diag-text` shipped `Copier le diagnostic` as its literal. A literal in
`popup.html` is painted before `popup.js` can translate it, so every English
install flashed French on every open, then settled correctly a few milliseconds
later. The product was right and briefly lied about it.

Measured rather than assumed: `scripts/measure_first_paint.py` loads the real
popup.html in the real Comet twice - once with script execution disabled, which
is exactly the first frame - and compares six elements. Only `#diag-text` moved,
so the flash was specific rather than a harness artefact.

New live gate check, proven red on sabotage: `@check` was missing, so the check
ran without ever recording a result - 17 executed, 16 counted, verdict READY
while the flash was present.

 - the badge is the first thing read, and the only thing that went stale

`checkRelay()` ran exactly once, in `init()`. The 30s interval refreshed only the
session counter. So a relay that died after the popup opened - or a Lightpanda
that restarted - kept showing "Relay Online" for as long as the panel stayed
open, and the third state added in v0.6.1 (relay alive, CDP dead) was unreachable
except in the few hundred milliseconds after opening.

The interval now re-checks the relay too, and a `visibilitychange` listener
re-checks on the way back in - the moment a user most often reacts to something
having just broken. Bursts are coalesced behind a 2s floor, and a hidden or
unpaired popup still spends nothing.

## [0.7.14] - a route can widen the deadline it inherited, only on the record

`Handler.timeout` (15s) is the backstop that releases a silent socket. A route
may narrow it - five do, at 10s - but a route that *widens* it reopens the hole
the class deadline closed: one client holds a thread for as long as that route
allows. `/v1/cdp` legitimately widens to 30s (the only route that makes the relay
talk to Lightpanda). That exemption now lives in a constant, with five tests
around it, each proven red.

Writing the test found the shape the audit had guessed at: `self.path ==`, not
`path ==`, and a `settimeout` inside a route body sits 15 lines below its branch
header, so "the last route mentioned before the call" attributed it to nothing.

## [0.7.14 - addendum] - the rate-limit message named the wrong quota

`_RATE_HINT` was a constant saying "anonymous is 60/hour per IP", raised on every
403/429. A user holding a valid token - which raises the quota to 5000/h - was
told to add a token they already had. The figures now come from the error's own
`X-RateLimit-*` headers, and the caller's identity from GitHub's number (60 =
anonymous), not from the local token file.


## [0.7.13] - a client that can wait forever has no honest state to be in

The popup had eight `fetch()` calls and one deadline, on the import path only.
`/v1/bootstrap` runs first, so a relay that accepted the socket and went silent
left the badge on "Checking…" forever and `/health` was never even tried. All
eight now go through one `relayFetch` helper carrying a cancellable signal.

The deadline is 45 s on purpose: the relay cuts a body read at 10 s and its class
deadline is 15 s, and a client that aborts first turns a translated reason into a
bare `Failed to fetch`.

Relay error codes were rendered verbatim — "origin refused" inside a French
popup. Nine codes are now mapped to i18n keys in ten languages, and the gate
reads the codes out of `relay/server.py` so a new one fails instead of shipping
untranslated.

## [0.7.12] - a client that never spoke could never be released

- `Handler` had no class-level `timeout`, so `StreamRequestHandler.setup()` left
  every accepted socket blocking. The `settimeout(10)` inside `do_GET` ran too
  late: it executed after `handle_one_request` had already read the request line
  and headers, which is exactly the read a client holds open by sending nothing.
  Measured: 25 connections that transmitted zero bytes stayed open past 35s
  while `/health` kept answering 200 - thread and memory exhaustion, not a hang,
  so nothing ever looked broken.
- The deadline is per socket operation, NOT a cap on the request's duration.
  `tests/test_socket_timeout.py` pins both halves: a truncated request is
  released at the deadline, and a handler that runs 2x past it still receives a
  complete response. The CDP import path (navigate + 1.5s settle + four
  injection rounds) legitimately outlives the deadline, and a total-duration cap
  would have broken it with every unit test still green.
- New gate check (30th, LIVE): drives a silent socket against the RUNNING relay
  and reports the measured release time plus `/health` still 200 afterwards.
- The first version of that test subclassed `Handler` with `timeout = 2` to stay
  fast, which made it blind to the production constant - sabotaging
  `Handler.timeout` to 600s left all five tests green. Speed now comes from
  scaling the wait to the real deadline, never from replacing it.

## [0.7.11] - a read that a careless writer could still crash

- `list_sessions` snapshotted the sessions dict with `for origin, cookies in
  _SYNCED_SESSIONS.items()`. That form raises `RuntimeError: dictionary changed
  size during iteration` if the dict changes mid-loop. Linux CI produced it; three
  consecutive local runs did not, so the v0.7.9 fix shipped as "green" while the
  shape was still crashable. `list(d.items())` takes the snapshot in one C-level
  pass and cannot raise. The lock remains the contract; this is defence in depth.

## [0.7.10] - the diagnostic report exported the tab URL, token and all

- `copyDiagnostic` promised "no cookie, no token, no URL" in its own comment and
  then copied `currentTab.url` whole. That URL routinely carries `?access_token=`,
  `#access_token=` or a session id, so a "no secret" report pushed the credential
  into a paste-anywhere clipboard. The report now carries the origin only, via a
  `reportableOrigin` helper - the same narrowing the sync path already did.
- New gate check (29th, LOCAL): runs the real `const report = [...]` array out of
  `popup.js` through a real URL parser over 8 URL shapes, so it cannot pass on a
  report scrubbed in only some code path.
- A delegated audit reported the bootstrap endpoint as CRITICAL - claiming a
  forged `Origin` header receives the shared secret, "proved live". Re-tested in
  isolation: a made-up 32-char extension id gets 403 and writes no pin; only the
  official id passes. The audit's probe had already pinned the forged id first, so
  it was measuring the poisoning scenario while describing the default one.

## [0.7.9] - one lock per dict: the session race only failed on Linux

- v0.7.7 fixed `dictionary changed size during iteration` by taking `CDP_LOCK` in
  `list_sessions`, but `clear_sessions` and the persisted-session restore mutate
  the same dict under a DIFFERENT lock. Two locks guarding one dict protect
  nothing. Linux CI caught it - Windows never did, because the GIL and the thread
  scheduling made the window unobservable locally. All readers and writers of
  `_SYNCED_SESSIONS` now go through a single `SESSIONS_LOCK`; `/health` reads its
  count through `session_count()`.
- The concurrency test mutated the dict bare, a state no production caller can
  produce, so it tested the harness rather than the shipped locking. It now
  mutates under the lock, and a second test proves the read path survives a
  writer that does NOT take the lock at all - a read must be robust to a
  careless writer, not merely hope it is disciplined.
- The AST guard that pins this only inspected assignments, so putting the reader
  back under `CDP_LOCK` left it green. It now walks every `Name`, `Attribute` and
  `Subscript` touching the dict, and the sabotage names the offending line.

## [0.7.8] - the DNS verdict cache had a TTL but was never pruned

- `_DNS_CACHE` had `_DNS_CACHE_TTL`, but the TTL only decided when an entry was
  STALE. Nothing ever removed one, so the dict grew for the lifetime of the relay -
  one entry per distinct hostname ever submitted to the origin check. A single
  site minting unique subdomains (asset hosts, tracking domains, cache busters)
  grows it without bound. Writes now go through `_dns_cache_put`, which purges
  stale entries and caps the dict at 512, evicting the oldest when full.
- The first version of the test called `_dns_cache_put` directly and stayed green
  with both production call sites reverted to the raw dict assignment - six
  decorative tests. Rewritten to drive `valid_origin()`, the function a request
  actually traverses.

## [0.7.7] - the undo point could be destroyed before it existed

- `_backup` did `rmtree(backup_root)` BEFORE rebuilding it, so any failure during
  the copy - ENOSPC, EPERM, or a file lock, which is the NORMAL case on Windows
  when Chrome holds `popup.js` open - left the install with no undo point at all.
  It now builds in `extension-backup.new` and swaps at the end, cleaning both the
  staging and the retired generation in a `finally`.
- `apply_update`, `rollback_update` and `check_update` took no lock. The relay is
  a ThreadingHTTPServer and three callers reach the module concurrently (popup,
  an agent with the token, `--apply-update`). All three now serialize on
  `_UPDATE_LOCK`, an **RLock** because `apply_update` calls `check_update` and a
  plain `Lock` deadlocks the request thread against itself.
- `_mirror` skips `.build-info.json` by design, so the backup never carried it:
  a rollback restored a tree with blank provenance. It is now copied explicitly.
- `meta.json` was filled from `installed_info()` re-read AFTER the mirror, so it
  described the NEW install instead of the one the backup can restore. The info is
  now snapshotted before mirroring. Found in production: the report said
  `version: None` while `installed_info()` said `0.7.6`.

## [0.7.6] - the document-start restore scripts stacked, and "Tout retirer" left half the session

- Every import registered a `Page.addScriptToEvaluateOnNewDocument` holding a full
  copy of the localStorage snapshot, and nothing ever called
  `Page.removeScriptToEvaluateOnNewDocument`. The scripts therefore stacked for
  the lifetime of the CDP connection - measured: 3 imports, 3 live scripts - each
  one re-writing the whole snapshot on every future page load. The relay now keeps
  the identifier of the live script and retires the previous one on each import.
- `clear_sessions` deleted the cookies by name but left the restore script
  registered, so every subsequent page load put the entire localStorage back:
  "Tout retirer" was a half-wipe, and a partial wipe is indistinguishable from a
  flaky sync. It now retires the script as well.
- `_backup()` writes `meta.json` INTO the backup directory and `rollback_update()`
  mirrors that directory into the live extension, but `_mirror` exempted only
  `.build-info.json` - so a rollback deposited a stray config file in the shipped
  tree, which the next update's prune then deleted as "not in the source tree".
  Both bookkeeping files now come from one `MIRROR_KEEP` constant, and the
  filename is no longer hard-coded at its two use sites.

The identifier assignment was initially missing its `global`, which wrote a local
and left the module-level slot empty - caught by the probe showing zero removals
after the first fix, not by the suite.

203 tests green, acceptance gate 28/28.

## [0.7.5] - the CDP proxy was handing out cookie values over HTTP

- `POST /v1/cdp {"method": "Network.getCookies"}` answered 200 with the whole
  cookie jar **including values** - measured live, 7 cookies - to anyone holding
  the token. `/v1/cdp` returned `proxy_cdp()`'s result verbatim and the blocklist
  only covered `Browser.close`, `Target.disposeBrowserContext` and
  `Network.deleteCookies`. This was the single route where a cookie value could
  reach an HTTP response. `Network.getAllCookies`, `Network.clearBrowserCookies`,
  `Storage.clearCookies`, `Storage.clearDataForOrigin` and
  `Storage.clearDataForStorageKey` are now refused too - the last two could wipe
  the storage of every synced origin while `clear_sessions` scopes the same job
  per origin. Agents that genuinely need to know whether a cookie is present get
  the new `route: "verify_cookie_names"`, which returns names only.
- `list_sessions()` iterated `_SYNCED_SESSIONS` with no lock while
  `clear_sessions` mutated it under `CDP_LOCK`: `RuntimeError: dictionary
  changed size during iteration`, 24 times in 2 seconds when measured. It now
  iterates a snapshot taken under the lock.
- `set_session` reset only two of its four per-request counters before the early
  `raise`s, so a refused import answered 400 with the PREVIOUS site's numbers:
  `storage_expected = 7` and `storage_missing = ['user','cart','tok']` for a
  payload carrying one key, rendered verbatim by the popup.
- `_authorized()` let `_load_secret()`'s PermissionError escape: the client got a
  connection reset instead of a 401, reachable unauthenticated on every guarded
  route. It now never raises, and compares bytes on both sides.
- `do_GET` had no socket timeout while `do_POST` had three, so a relay that
  accepted the socket and never answered wedged the popup on "Checking..." forever.
- `#toast` sits AFTER `<script src="popup.js">` in the document and the element
  was captured at module load, so it was null for the whole session and every
  `showToast()` was a silent no-op: "Tout retirer" cleared without confirming,
  and copy-diagnostic feedback was invisible. The lookup is now lazy.

196 tests green, acceptance gate 28/28, popup still 563 px.

## [0.7.4] - four audit findings, three of them real

- `__Host-` cookies were not forced Secure (RFC 6265bis). The branch forced
  `path=/` and dropped `domain` but left `secure` untouched, so a supplied
  `secure: false` downgraded the one prefix whose entire guarantee is
  "Secure, host-only, path=/". `__Secure-` was already forced.
- `artifacts.session_state` in the support report was permanently `unset`:
  `collect()` looked for `session_state_path` in `updater.py`, but it lives in
  `server.py` as `_session_state_path`. The report claimed the cookie file was
  absent on machines where it existed, holding the cookies.
- One torn line in `update.log` discarded the entire install history: the parser
  was a single list comprehension, so one truncated line (a power cut during an
  unsynchronised append) returned `[]`. Parsing is now per line.
- `/v1/sessions` `expires` was dead by construction: `cookie_for_cdp` pops
  `expires` (Lightpanda drops cookies set with one) and `list_sessions` read
  that same key, so expiry was always null and `expired` always false - the
  popup could never warn about a stale session. The lifetime is now preserved as
  `expires_hint`, stripped again on the way to CDP.

Rejected after verification: a nested `sub/D:evil.js` drive-relative escape
(`_safe_members` already refuses it), and cookie values reaching CDP unbounded
from the extension's own browser API (the extension is the trust boundary; a
value cap belongs at the extension, not only the relay).

Two existing tests were asserting a shape production never stores (they wrote
`expires` straight into the dict), so they stayed green while `/v1/sessions`
reported null forever. They now build cookies through `cookie_for_cdp`.

184 tests green, acceptance gate 28/28.

## [0.7.3] - the restored session can no longer be injected twice

- `_restore_persisted_session()` is reached from the CDP proxy AND from the
  session-import handler, i.e. two ThreadingHTTPServer threads. It read
  `_PERSISTED_APPLIED`, then released every lock, then made the CDP call, then
  set the flag. Both threads could pass the check in between, and both called
  `_apply_session` - and `_apply_session` SETS cookies rather than replacing
  them, so Lightpanda's jar was populated twice. The `StateLock` claim is now
  taken under the lock before the call, released on success and on failure.
- `CDP_LOCK` was never the right lock for this: it guards the socket, not the
  "has this already been done?" question.
- The `except Exception: return False` is gone. It made a structurally broken
  restore indistinguishable from "Lightpanda is down, retry later", and the
  relay went on reporting a session it had never injected. Transient failures
  still surface as the retryable types both callers already handle; the claim is
  released either way, so a later call retries.
- `_LAST_SESSION` is now snapshotted (copied) before use, so a caller cannot
  change the relay's own copy mid-apply.
- `tests/test_restore_race.py`: two threads, the first held inside the "CDP
  call". Proven red both ways - removing the claim gives `_apply_session ran 2
  times for ONE restored session`, and restoring the old `except` gives
  `ValueError not raised`.

169 tests green, acceptance gate 28/28, E2E verified after a relay restart
(import 200, `attached: true`, `cdp_attached: true`, no cookie values in the
report).

## [0.7.2] - the archive guard is now proven, not assumed

- `tests/test_archive_windows_paths.py`: the traversal tests only ever asked
  about `../../evil.txt` and `/etc/evil.txt`. The guard in `_safe_members`
  normalises backslashes, refuses drive letters and therefore also catches
  `C:/evil.txt`, `C:\evil.txt`, `C:evil.txt`, `//server/share/...` and
  `..\evil.txt` - none of it asserted. A "simplification" to a plain
  `name.startswith("/")` check would have passed all 56 updater tests and
  reopened the hole on the only platform this ships on. Proven red by making
  validation per-member instead of up-front: all four Windows shapes were then
  extracted silently.
- Also asserted: a refused archive leaves NO partially extracted tree, and a
  valid archive still lands exactly where expected (a guard that refuses
  everything is not a fix).

No product code changed. 166 tests, all green.

## [0.7.1] - the support report stopped describing a module that never ran

- `_sibling("server")` imported a SECOND copy of `relay/server.py`. In the live
  daemon `server.py` is the entry point, so its module is registered under
  `__main__` and `sys.modules` holds no `server` key at all. The report read the
  fresh copy's globals, which are always empty. Live symptom: `/health` said
  `attached: true, sessions: 1` while `/v1/diagnostics` said `cdp_attached:
  false, synced_origins: 0, cdp_transport: "NoneType"` - same process, same
  instant, opposite answers. Now `__main__` is reused when it really is the
  relay (compared by path, so a test runner as `__main__` cannot hijack it).
- `RelayServer` requests `SO_EXCLUSIVEADDRUSE`. `allow_reuse_address = False`
  only clears SO_REUSEADDR, which does NOT stop a second process binding an
  already-listening socket - two relays were live at once, each holding its own
  copy of the session state.
- `health_payload()` no longer raises on a transport object without `alive()`.
  `do_GET` has no try around it, so the AttributeError killed the HTTP thread
  instead of answering.
- The watchdog checked only that `/health` answered 200, so it called a relay
  with a dead CDP connection healthy, and it restarted the relay when only
  Lightpanda was down. It now requires `attached: true`, and a dead Lightpanda
  is logged instead of triggering a restart (the relay connects on demand).

Tests: `test_single_relay.py` (4), `test_watchdog_health.py` (8), 2 new in
`test_diagnostics.py`. 161 total, all green. Every fix proven red without it.

## [0.7.0] - the popup finally shows what /health reports

- `checkRelay()` looked only at `res.ok`, so v0.6.1's honest `attached: false`
  never reached the user: the badge still read "Relay Online" over a dead CDP
  connection. It now reads the field and shows a third state.
- New `badge.idle` style (amber). Not green - the relay is up. Not red - nothing
  is broken. The relay answers; Lightpanda is simply not attached yet.
- New `relayIdle` key in all 10 languages, kept short ("Non connecté") because
  "Relais prêt - navigateur non connecté" was clipped inside the pill.
- `preview_popup.py --state idle` renders that state, so a UI state with no
  screenshot cannot go unreviewed again.
- The acceptance gate's i18n check now also catches `t("key")` double-quoted
  calls and "two keys on one line" (an insert that ate a comma).
- `--apply-update --channel release|main|auto`: `--apply-update` silently
  followed `check_update`'s recommendation, so asking for the published release
  could install the main-channel tarball instead - whose sha256 has no sidecar,
  which it reported as `checksum_verified: false` with no way to ask otherwise.

Tests: 147 green, gate 28/28, CI green.

## [0.6.1] - /health stops lying about a dead connection

- `CdpTransport` learns when its socket died (OSError, graceful close, or a peer
  that streams events forever without answering) and reports `alive()`.
- `_ensure_connection` reopens a transport that proved it is dead. It used to
  return early on any non-`None` transport, so after a Lightpanda/WSL restart the
  relay kept a dead socket forever and only an explicit resync recovered. A
  healthy idle connection is still preserved - Lightpanda scopes its cookie jar
  per connection, so tearing that down logs the user out of every session.
- `/health` derives `attached` from the transport instead of a flag never cleared
  on death, and reports the synced-session count. It answered `200 attached=true`
  over a connection that could not carry a byte - the same class of lie as
  v0.5.7's never-ending spinner.
- `CdpTransport.request` bounds the unsolicited-event skip loop
  (`MAX_SKIPPED_EVENTS = 2000`) so a page logging hard cannot hold the serving
  thread until the socket timeout.

Tests: `tests/test_health_truth.py` (9). 147 total, all green.

# Changelog

## [0.6.0] - 2026-10-02
### Added
- **Copy diagnostic** (footer of the popup): one click puts a sanitized report
  on the clipboard - versions, counts, file fingerprints, live relay state, last
  installs. A failed sync used to end at a screenshot with nothing to act on.
  No cookie value, no token, no URL: `relay/diagnostics.py` owns that guarantee
  and both its unit tests and the acceptance gate plant credentials to prove it.
- `GET /v1/diagnostics` returns the same report as json + text.

### Fixed (v0.6.0, second pass)
- `/v1/diagnostics` answered 500 `ModuleNotFoundError` on the live relay while
  every test was green: `relay/` is not a package, so the running process
  imports its neighbours flat (`import updater`) and the dotted
  `from relay import diagnostics` did not resolve. Both spellings now work.
- Importing flat and then dotted loaded the file twice under two names, so the
  report read a second, empty copy of the relay module and answered "0 cookies"
  while the relay held 12. `_sibling()` now reuses the instance already in
  `sys.modules`. Covered by three new tests, verified red.

### Fixed
- **The release archive is now reproducible.** It was rebuilt from the same tree
  into a different sha256, because `ZipFile.write` stamped the build time and OS
  into every entry and because deflate is not reproducible across build machines
  (.venv ships zlib 1.3.1, the system python ships 1.3.1.zlib-ng - same 148 KB
  tree, 148120 vs 148524 bytes). Entries are now STORED with a fixed epoch, a
  fixed creator and no host metadata: one sha256 per tree, on every machine.
- `scripts/build_release_zip.py` died with a bare `FileNotFoundError` when
  `LOCALAPPDATA/Temp` did not exist (fresh profile, CI, non-Windows).
- Removed `relay/patch_snippet.txt`, a tracked scratch file.

## [0.5.8] - 2026-09-14
### Fixed
- `WinError 10053` shown raw in the popup ("Transfert incomplet : 0/8"): the
  storage injector caught the connection error before the 0.5.7 resync could
  see it. It now propagates - socket dies *during* injection, resync, retry.
- Page-level failures report short codes (`verify-error:Name`) translated into
  10 languages, never the OS's raw localized sentence.

## [0.5.7] - 2026-09-14
### Fixed
- **The sync could hang on "Transferring & verifying…" forever.** When WSL or Lightpanda restarted under the relay, the daemon's single CDP WebSocket died and every `/v1/session/import` failed in milliseconds (`WinError 10053` at storage-verify) - but only `proxy_cdp` had the resync-and-retry; the import path did not, so nothing revived the socket except using the agent proxy by chance. `set_session()` now resyncs and retries once on a dead connection, like the proxy always did (`tests/test_import_resync.py` proves it: red without the fix, green with). The popup additionally gets a hard 30s deadline on the import fetch (`errRelayTimeout`, all ten languages): a client waiting forever has no honest state to show, so the sync now always ends - pass, fail, or say the relay is stuck.

## [0.5.6] - 2026-09-10
### Fixed
- **Three languages rendered the string "undefined".** The Chinese, Japanese and Arabic blocks were each missing `clearConfirm` and `clearedToast`, so the tooltip on the clear button and the toast after clearing showed `undefined`. Every other language had them; nothing compared the key sets, the old test only checked a hand-picked list of *update* strings. The whole key set is now compared across all ten languages, and every `t('...')` call in `popup.js` is resolved against all ten.
### Fixed (packaging)
- **The published v0.5.6 zip carried this machine's install history.** `build_release_zip.py` walked `extension/` on disk, so the gitignored `extension/.build-info.json` - its commit, its timestamp, its previous install - went into a public download. The builder now ships what git tracks, the asset was rebuilt (14 files, `8104c4bf…f110`) and re-uploaded, and the gate compares the published archive against `HEAD` byte for byte, so a zip that is not the committed tree can no longer pass.

### Added
- **`scripts/acceptance.py`, the gate that runs before anything is committed.** 24 checks over the seams the unit tests cannot see: version agreement across manifest/pyproject/updates.xml/CHANGELOG/release notes, LF shipped tree, no scaffolding in the shipped tree, id literals that are not the pinned 32-character id, the shared secret absent from every file, i18n parity, every DOM id `popup.js` touches existing in `popup.html`, the popup's live height against Chrome's 600px cap, then the live system: relay auth (401/403/200), the release asset downloading and matching its published sha256, the main-channel tarball, the CDP proxy, a real session import round-trip, and the extension in Comet serving the repo version. `--local` runs without any service. GitHub Actions runs the local half on every push.
- The gate found and this release fixes the i18n bug above, plus a second 33-character extension id in `scripts/verify_extension.py` - the script whose `chrome-error://chromewebdata/` output had been worked around instead of fixed - and a hardcoded expected version of "0.4.3" in the same script, which reported twelve later releases as broken.
- `scripts/cdp_utils.py`: one shared resolver for the extension id (the copy-paste is what broke twice) and for the CDP plumbing, used by both scripts. `tests/test_tooling.py` guards the class: wrong-length ids refused, no id literal in a script, no expected version hardcoded, no Windows CLI read with `text=True`.
- `bridge.py` decoded Windows CLI output with `text=True` (utf-8) in two places. `wsl.exe -l -q` writes UTF-16LE and `netstat` writes cp850 on a French install: one garbled the distro list, the other killed the reader thread and returned `None`. One tolerant decoder now handles both.
- The relay reports *why* GitHub could not be reached: "GitHub API rate limit reached (anonymous is 60/hour per IP)" with `error_kind: rate_limit`, instead of "GitHub unreachable (RuntimeError)". The check cache went from 60s to 5 minutes for the same reason. `SECURITY.md` documents the optional `~/.config/lightpanda-bridge/github_token`.
- The acceptance gate runs the unit suite with the project's own interpreter: a bare `python` without `websocket-client` made two modules fail to import and the suite report 56 tests instead of 111.

## [0.5.5] - 2026-09-10
### Fixed
- **"Install the latest commit" failed with `HTTP Error 415: Unsupported Media Type`.** The main channel reused the `Accept: application/octet-stream` header that was written for the CDN that serves release assets, but the archive comes from `api.github.com/repos/.../tarball/<sha>` - and the API refuses a media type it cannot produce. GitHub answered 415 before sending a single byte, so the button did nothing. Measured on the same URL: octet-stream -> **415**, `application/vnd.github+json` -> **200**, no Accept header at all -> **200**.
- The guard now lives in `_fetch` - the one place every update request goes through - so the API host always receives the GitHub media type and no caller can reintroduce the bug by asking for bytes. Download hosts keep the caller's Accept, because the CDN does serve octet-stream. The release channel worked all along; only the main channel was broken.
- 3 new tests pin it, including a behavioural one that captures the real header on a stubbed socket: **95 tests, 1 skipped**.
- **Hygiene:** `.gitattributes` pins LF for `extension/**`, so a Windows checkout, the release zip and an update install are byte-for-byte the same tree. Before this, a successful update rewrote every file (content identical, line endings not) and `git status` reported the whole extension as modified.
- **Tooling:** `scripts/reload_extension.py` now reads the extension id from the relay's pin (a hardcoded 33-char id made it reload nothing while printing success) and reloads through `chrome.developerPrivate.reload()` - `chrome.runtime.reload()` from inside the popup does not pick up a new manifest.
- **Traceability:** every install appends one JSON line to `update.log` (version, commit shas, artifact, file counts, timestamp; never a cookie, a token or a URL).

## [0.5.4] - 2026-09-10
### Fixed
- **The update card's buttons were cut off - the button existed, but it was past the fold.** Chrome caps a popup at 600px tall. The body was pinned to `max-height: 580px` with `overflow: hidden`, and the real content needed ~590px: the button row landed below the cap and was sliced in half. The body now scrolls instead of hiding, and the vertical density was trimmed so the whole popup fits in **563px** in its default state, footer included.
- **The full-width red "Clear all" bar is gone.** It sat alone on its own row at the bottom of the sessions card, where it read as a misplaced primary action. It is now a compact danger pill in the card header, next to the count badge, and it turns solid red once armed.
- **The "clear all" button lost its inner `<span>` on the first click.** The handler wrote `textContent` on the `<button>` itself, which replaced its markup and detached the label node. The label is now always written to the span; the full sentence ("click again to clear all") moves to the tooltip.
- **The commit hash was printed twice** - once in the blue chip, once in the line below. The chip now carries the STATE only (`Update` / `Up to date`) and the line below carries the target (`-> commit a478b90`), so no information repeats.
- **Two long labels no longer fight over one 430px row**: the rollback action is a 38px icon button, with the sentence as its tooltip and `aria-label`.
- The collapsible sessions card moved to the end of the popup, so opening the list only grows the tail; the list scrolls inside a capped area (132px) instead of pushing the layout.
### Added
- `scripts/diagnostics/preview_popup.py` - renders the popup in headless Chrome against a stubbed `chrome` API, prints the measured height of every block, and **exits 1** when the default state does not fit under the cap. The layout is now verifiable without a live browser.
- 6 layout regression tests pin the fix (hidden overflow behind a fixed cap, compact pill in the header, collapsible card last, no chip/meta duplication): **92 tests, 1 skipped**.

## [0.5.3] - 2026-09-10
### Fixed
- **x.com could never sync - "5/7 localStorage keys" that no re-sync could clear.** x.com keeps two of its entries under 194-character names (`rweb.sessionBinding.hashClaim:<base64>`). The snapshot filter dropped every key name longer than 128 characters **silently**, so those two were removed before the first write attempt: Lightpanda received 5 of 7, the popup honestly said so, and syncing again could never help because the missing keys never left the relay. Key names up to 1024 characters and values up to 256 KiB are now carried, with the whole snapshot bounded at 1.5 MB so it still fits the import body cap.
- **Nothing is dropped in silence any more.** A key the relay cannot carry - name or value past the bounds, or a snapshot past the total - is reported BY NAME with its size and the reason, on both the HTTP and CLI paths, instead of turning into a ratio that never reaches 100%. The incomplete-transfer message names the missing keys as well, and the popup has a translated message for a refusal.
### Added
- `storage_expected`, `storage_missing` and `storage_refused` in the import response (success *and* failure), so the popup builds a specific, translated message instead of showing the relay's raw text.
- Tests: `StoragePlanTests` plus named-refusal, named-partial and legacy-integer-verify cases - 86 tests, 1 skipped.
- Proven end to end on x.com: the live tab's session was imported through the real `/v1/session/import`, then checked **inside** Lightpanda - 7/7 keys present including the two 194-character names, zero extras, `x.com/home` loaded as the logged-in account, and the session survived two further navigations. Key names and sizes only, never a value.

## [0.5.2] - 2026-09-10
### Fixed
- **"Échec de la mise à jour : update redirect refused" — the update could never install.** GitHub answers a release-asset request with a 302 to a signed CDN URL, and it now redirects to `release-assets.githubusercontent.com`. That host was missing from the download allow-list, so the guard added in 0.5.0 rejected GitHub's own redirect and every install aborted. The current CDN host plus the two historical ones are now allow-listed; the check still runs on the **final** URL, so a redirect still cannot walk the download off GitHub, and a lookalike host (`release-assets.githubusercontent.com.evil.example`) is still refused.
### Added
- `tests/test_updater.py`: 8 tests for the download path against a fake HTTP layer — accepted CDN hosts, redirect off GitHub refused, redirect to plain http refused, lookalike host refused, non-GitHub source refused, oversized download refused by header *and* by body, and the allow-list contains no wildcard. Verified end to end against the real GitHub release: zip downloaded, `sha256` matched the published sidecar, tree installed, provenance written, rollback backup kept.

## [0.5.1] - 2026-09-10
### Changed
- When the deployed copy carries no provenance (installed by hand, or by an installer older than 0.5.0) and the release is not older, the button now installs the **tagged release artifact** — the immutable one with a published `sha256` — instead of the `main` snapshot. The `main` channel is still used when the checkout is ahead of the last release, so an update can never silently downgrade content.
### Added
- Tests: the unknown-baseline choice (release vs main), and the no-downgrade rule.

## [0.5.0] - 2026-09-10
### Added
- **An update button, and a badge that makes an update impossible to miss.** The popup compares the deployed version with GitHub and shows a *Update to vX.Y.Z* button when a release is ahead, or *Install the latest commit* when `main` has moved on. The toolbar badge appears on its own (checked every 3 h, on install and on browser start).
- **The relay installs it, because the extension cannot update itself.** `GET /v1/update/check`, `POST /v1/update/apply` and `POST /v1/update/rollback`, plus the same three operations as `python relay/server.py --check-update | --apply-update | --rollback-update`. The archive is downloaded from a compiled-in repository (never from the caller), restricted to GitHub hosts over https, size-capped, refused if it contains traversal or absolute paths, and refused unless it holds a Manifest V3 `manifest.json` whose name is this extension. A published `.zip.sha256` sidecar is verified when present, the previous tree is backed up outside the repository, and *Undo* puts it back.
- The footer version is now read from the manifest at runtime instead of being hand-edited in `popup.html` on each bump.
### Changed
- The extension requests the `alarms` permission for the periodic update check.
### Fixed
- `relay/server.py --self-test` also covers the version ordering, the archive traversal refusal and the incomplete-tree refusal.

All notable changes to the Lightpanda Session Bridge will be documented in this file.

## [0.4.3] - 2026-09-10
### Fixed
- **A partial `localStorage` snapshot is no longer reported as a success.** The import was satisfied with "some keys landed": a real `a6api.com` sync moved **17 of 29 keys**, `user` was among the dropped ones, every authenticated call then answered **407 `New-Api-User`**, and the popup still said "synchronized" — the reason a session seemingly only worked *after a second sync*. Keys are now verified **one by one** (4 attempts, with a page reload in between so the durable restore replays the snapshot), and an incomplete transfer fails loudly with the ratio: `localStorage transfer incomplete: 17/29 keys verified`.
- **The popup no longer swallows a `localStorage` extraction failure.** `chrome.scripting.executeScript` errors were caught and ignored, so a sync could silently leave with cookies only; extraction is retried, a failure is now an explicit translated error (`errStorageExtract`), and a short `storage_count` returned by the relay is refused client-side as well (`errPartialStorage`).
- **Session survives a relay restart / reboot / watchdog restart.** The synced session lived only in memory, so a restart emptied the jar while `/health` still answered `{"ok": true}` and agents silently ran unauthenticated. The session is now persisted to `~/.config/lightpanda-bridge/session.json` (owner-only, cookie values never logged) and re-applied at startup, with a retry on every call until Lightpanda answers.
- **`localStorage` now survives any later navigation.** Injecting after a navigation was still lost by the *next* one (Lightpanda keeps it in the page context); a document-start restore is registered once, so the snapshot is re-applied on every new document.
- **Cookies whose `secure` flag does not match the URL scheme are found again** — the `session` cookie of a6api is `secure: false`, and Chrome only exposes a cookie to `chrome.cookies` when a host permission covers its origin scheme: `host_permissions` now includes `http://*/*`, the popup falls back to a domain query, and an empty jar is told apart from an out-of-scope one (`errCookiesOutOfScope`).
- **Relay startup could fail silently**: `UnicodeEncodeError` (cp1252 console encoding of `✓`) killed `bridge.py start` before the launch step, and a stray interpreter without `websocket-client` failed instantly. Both streams are reconfigured to UTF-8 and the launcher picks an interpreter that can actually import the relay's dependencies.
- Only one relay can bind the port now (`allow_reuse_address` disabled): on Windows `SO_REUSEADDR` let a second, session-less relay answer `attached: false` alongside the real one.
- `clear_sessions` counted the wrong entries and now also erases the persisted state on disk.
### Added
- The success message reports both halves of the transfer: `✓ Session synchronized (N cookies, M localStorage keys)` — translated in all 10 popup languages, alongside the two new error strings.
- `scripts/verify_live.sh`: one-shot live check of the relay (health, unauthenticated `401`, foreign-origin `403`, banner) that never prints a secret.
- `scripts/diagnostics/`: the read-only scripts that pinned the a6api chain down (key names and HTTP codes only, never a cookie value or a token).
### Security
- Extension-origin check hardened (pinned extension ID + allow-list), the relay no longer advertises itself in a `Server:` banner, `/clear` bodies are size-bounded, and `SECURITY.md` documents the applied hardening and the two accepted risks model ("one user per machine", TOFU).

## [0.4.2] - 2026-09-08
### Fixed
- Sessions panel now refreshes **immediately after a successful sync** (counter and list update without any click) and auto-expands to show the newly synced site.
- Counter refreshes on every popup open even while the panel is collapsed.
## [0.4.1] - 2026-09-08
### Added
- **Session manager in the popup**: see which sites have active sessions inside Lightpanda (origin, cookie count, nearest expiry — never cookie values), remove a single site's session, or clear everything at once.
- Relay endpoints: `GET /v1/sessions` (sanitized list, token-required) and `POST /v1/sessions/clear` (per-origin or all, token-required). Cookies are deleted from Lightpanda's jar over CDP.
- i18n: session manager translated in all 10 popup languages.
## [0.4.0] - 2026-09-08
### The zero-configuration release
- **Relay owns the only CDP connection.** Lightpanda scopes its cookie jar **per CDP connection** — an agent opening its own socket never saw synced sessions (the failure hit in practice on dev.to). The relay now keeps its connection for good and exposes `POST /v1/cdp` so every agent executes commands on the connection that holds the sessions. If Lightpanda restarts, the last session is replayed from memory automatically.
- **`bridge.py` one-command lifecycle**: `setup` (installs WSL2/Lightpanda/deps), `start` (idempotent), `status`, `doctor`, `install-browser-ext`.
- **`bridge_agent.py` SDK**: authenticated automation in 3 lines from any synced site; evaluation hardened with retry-on-None.
- **Import navigates the live target to the synced origin immediately** — the authenticated page is ready the moment the sync ends.
- `lightpanda_client.py` kept as a compatibility shim routed through the same proxy.

## [0.3.5] - 2026-09-08
### Fixed
- Relay: drop the `expires` attribute when injecting cookies — Lightpanda silently discards cookies carrying `expires`, which broke every transferred session (verified server-side: `logged-in` confirmed on dev.to after the fix).
- Cookie injection shape: explicit `Domain` + `httpOnly` + `Secure`, path `/`.
### Added
- `lightpanda_agent_session.py`: single-connection authenticated agent SDK. Lightpanda scopes its cookie jar per CDP connection, so the pulling/injecting/acting connection must be one and the same — this module encapsulates the working pattern (pull cookies from the desktop browser over loopback CDP, inject, navigate, evaluate with retry-on-None).

## [0.3.4] - 2026-09-08
### Added
- Automated token pairing via `/v1/bootstrap` restricted to `chrome-extension://` origins.
- `llms.txt` and `llms-full.txt` standard files for LLM documentation indexing.
- Continuous Integration workflow via GitHub Actions (`.github/workflows/ci.yml`).
- `pyproject.toml` standard packaging metadata.
- Citation support via `CITATION.cff`.
- Security policy (`SECURITY.md`) and Contribution guidelines (`CONTRIBUTING.md`).

### Fixed
- Enforce strict origin checking on secret-delivering bootstrap endpoints to block local CLI or malicious web script exfiltration.
- PascalCase normalization for CDP cookie `sameSite` parameters to eliminate `-31998 InvalidEnumTag` crashes.
- Bundled local fonts (`Space Grotesk`, `DM Sans`) to prevent third-party IP leakage.

## [0.3.3] - 2026-09-07
### Security
- DNS resolution validation before CDP WebSocket attachments with 60-second DNS caching (anti-SSRF / anti-TOCTOU).
- Elimination of `/v1/session/inspect` debugging leaks.
- Loopback-only socket binding (`127.0.0.1`).
