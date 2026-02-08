# Guide Docker - Projet Scoring Credit

**Auteur :** Gregory CRESPIN  
**Date :** 30/01/2026  
**Version :** 1.0

---

## Demarrage rapide

### Lancer Jupyter uniquement
```bash
docker-compose up --build
```

Puis ouvrir **http://localhost:8888** dans votre navigateur.

Le token par defaut est `credit2024`. Pour le modifier :
```bash
JUPYTER_TOKEN=mon_token docker-compose up
```

### Lancer Jupyter + MLflow UI
```bash
docker-compose --profile mlflow up --build
```

- **Jupyter Lab** : http://localhost:8888
- **MLflow UI** : http://localhost:5000

## Commandes utiles

### Reconstruire l'image (apres modification de requirements.txt)
```bash
docker-compose build --no-cache
```

### Lancer en arriere-plan
```bash
docker-compose up -d
```

### Arreter les conteneurs
```bash
docker-compose down
```

### Acceder au terminal du conteneur
```bash
docker-compose exec jupyter bash
```

### Lancer MLflow UI depuis le conteneur Jupyter
Dans un terminal Jupyter (File > New > Terminal) :
```bash
mlflow ui --host 0.0.0.0 --port 5000 --backend-store-uri file:/app/mlruns
```
Puis ouvrir http://localhost:5000 (le port est mappe si vous utilisez `--profile mlflow`).

## Structure des volumes

Le repertoire du projet est monte en volume dans `/app` :
- Les modifications dans les notebooks sont persistees
- Les donnees dans `data/` sont accessibles
- Les runs MLflow dans `mlruns/` sont sauvegardes
- Les modeles dans `models/` sont sauvegardes

## Variables d'environnement

| Variable | Defaut | Description |
|----------|--------|-------------|
| JUPYTER_TOKEN | credit2024 | Token pour acceder a Jupyter Lab |

## Depannage

### Le port 8888 est deja utilise
Modifier le mapping dans `docker-compose.yml` :
```yaml
ports:
  - "8889:8888"  # Utiliser le port 8889 sur l'hote
```

### Erreur de permission sur les fichiers
Sur Linux, vous pouvez avoir besoin d'ajuster les permissions :
```bash
sudo chown -R $USER:$USER .
```
