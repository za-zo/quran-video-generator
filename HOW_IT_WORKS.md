# Comment fonctionne Quran Video Generator ?

## C'est quoi ce projet ?

C'est un robot qui fabrique tout seul de courtes vidéos de récitations du
Coran. Tu lui donnes une liste d'audios (récitations) et une liste de
vidéos de fond (paysages : mer, forêt, désert…), et il produit des clips
prêts à publier sur TikTok, Instagram Reels ou YouTube Shorts. Chaque
clip fait environ 60 secondes : une récitation en voix off, posée sur un
fond vidéo apaisant.

## Les ingrédients nécessaires

Pour que le robot fonctionne, il a besoin de trois choses, rangées dans
une base de données MongoDB :

- **Les audios** : des fichiers MP3 de récitations coraniques, hébergés
  sur Internet (par exemple sur archive.org). Chaque audio a un nom,
  une URL, et une durée.
- **Les catégories** : des familles de vidéos de fond. Par exemple
  `sea` (mer), `forest` (forêt), `desert` (désert). Une catégorie
  regroupe plusieurs vidéos.
- **Les vidéos** : des fichiers MP4 de fond, hébergés sur Internet,
  rangés dans une catégorie. Chaque vidéo a une durée.

Tu ajoutes ces ingrédients via une interface web (la « webapp »). Une
fois qu'ils sont enregistrés, le robot peut tourner.

## Comment une vidéo est créée, étape par étape

### Étape 1 — Choisir un audio

Le robot regarde tous les audios enregistrés et prend **celui qui a été
le moins utilisé**. Si trois audios ont été utilisés 0 fois et deux ont
été utilisés 5 fois, il piochera obligatoirement parmi les trois
nouveaux avant de toucher aux deux autres. C'est la règle
« least-used first » (en français : « les moins utilisés d'abord »).

À égalité d'usage (par exemple, tous à 0), le robot choisit au hasard
pour faire varier les résultats. C'est comme tirer au sort dans un
chapeau, mais en évitant soigneusement les papiers déjà sortis.

### Étape 2 — Découper l'audio

Une fois l'audio choisi, le robot le découpe en plusieurs petits clips
de 60 secondes chacun. Si l'audio dure 5 minutes, il peut en tirer
jusqu'à 5 clips non-chevauchants.

**Le respect des ayat** : le robot ne coupe pas n'importe où. Il
analyse d'abord l'audio pour repérer les **silences naturels** — les
moments où le récitant fait une pause (fin d'une ayah). Ces silences
sont stockés une fois pour toutes dans la base. Ensuite, pour chaque
clip, le robot essaie de placer la fin du clip sur un silence proche,
pour ne pas couper une récitation en plein milieu d'une phrase.

Si aucun silence n'est trouvé dans une fenêtre de ±5 secondes autour de
la fin idéale, le robot garde la coupe mécanique — c'est un repli
gracieux, pas un échec.

### Étape 3 — Choisir les vidéos de fond

Pour chaque clip, le robot choisit une **catégorie** de vidéos de fond,
toujours en privilégiant les moins utilisées. Il y a aussi un
« cooldown » : si une catégorie a été utilisée dans les 3 derniers
clips, elle est temporairement écartée pour éviter la répétition.

Ensuite, dans la catégorie choisie, le robot sélectionne plusieurs
vidéos (toujours least-used first) jusqu'à ce que leur durée totale
couvre les 60 secondes du clip. Si la catégorie n'a pas assez de
vidéos, il peut réutiliser les mêmes (selon la configuration).

### Étape 4 — Assembler la vidéo

Le robot télécharge l'audio et les vidéos choisies dans un dossier
temporaire, puis appelle **FFmpeg** — un peu comme un chef qui mélange
les ingrédients. FFmpeg :

- normalise toutes les vidéos à la même résolution (1080×1920, format
  vertical pour Shorts/Reels/TikTok) ;
- les met bout à bout ;
- les coupe à la bonne durée (60 secondes) ;
- ajoute la piste audio par-dessus ;
- encode le tout en MP4.

Tout ça en une seule passe pour aller vite.

### Étape 5 — Publier

La vidéo finale est envoyée sur **Cloudinary** — un service d'hébergement
de médias. Cloudinary renvoie une URL publique que n'importe qui peut
ouvrir dans un navigateur. Le robot enregistre cette URL dans MongoDB,
associée au clip, pour pouvoir la retrouver plus tard.

Pendant tout ce processus, le robot affiche un journal lisible,
étape par étape, pour que tu saches exactement où il en est.

## Comment le système évite la répétition

Le robot garde un compteur `usage_count` pour chaque audio, catégorie et
vidéo. À chaque fois qu'un élément est utilisé dans un clip, son
compteur augmente de 1. Au prochain tour, le robot choisit en priorité
les éléments dont le compteur est le plus bas.

Il y a aussi un `last_used_at` (la date de dernière utilisation) qui
sert de tie-break : à égalité de compteur, l'élément utilisé il y a
plus longtemps est légèrement avantagé. Et pour les catégories, un
cooldown court-termemporaire empêche d'utiliser la même catégorie
plusieurs fois de suite.

Résultat : sur 50 clips générés, chaque audio et chaque catégorie sont
utilisés à peu près le même nombre de fois. Pas de boucle, pas de
répétition ennuyeuse.

## Où sont stockées les informations ?

- **MongoDB** : c'est le carnet de notes du robot. Il y enregistre la
  liste des audios, catégories, vidéos, les compteurs d'usage, les
  silences détectés, et l'historique de toutes les générations (ce
  qu'on appelle les « exécutions » et les « slices »).
- **Cloudinary** : c'est le coffre des vidéos. Les MP4 finaux y sont
  hébergés de façon permanente, accessibles par URL. Le robot ne
  garde aucune vidéo en local après une exécution.

## Schéma général

```
   ┌─────────────┐   ┌──────────────┐
   │   Audios    │   │ Catégories   │
   │  (MP3 URL)  │   │  + Vidéos    │
   │             │   │  (MP4 URL)   │
   └──────┬──────┘   └──────┬───────┘
          │                 │
          └────────┬────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │     PIPELINE        │
        │  (Python + FFmpeg)  │
        │                     │
        │  1. Choisir audio   │
        │  2. Découper (sil.)  │
        │  3. Choisir vidéos  │
        │  4. Assembler       │
        │  5. Uploader        │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  Vidéo finale MP4   │
        │  (URL Cloudinary)   │
        └─────────────────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │   MongoDB (méta)    │
        │  - exécutions        │
        │  - slices            │
        │  - compteurs d'usage │
        └─────────────────────┘
```

Le pipeline est lancé par GitHub Actions (un robot en ligne qui
déclenche le nôtre à heure fixe ou sur demande). Il tourne sur un
serveur éphémère : rien n'est conservé localement entre deux
exécutions, tout est dans MongoDB et Cloudinary.
