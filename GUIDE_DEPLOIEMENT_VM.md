# Configuration CI/CD avec Déploiement Distant

Ce guide explique comment configurer le déploiement automatique sur un serveur distant via GitHub Actions.

## Architecture

```
GitHub (Push main/dev)
  ↓
GitHub Actions CI (tests)
  ↓
GitHub Actions CD (déploiement SSH)
  ↓
Serveur Distant (Docker Compose)
```

## Prérequis

- Serveur distant avec Docker et Docker Compose installés
- Clé SSH pour accéder au serveur
- Accès SSH configuré (port 22 ou custom)

## Configuration sur le Serveur Distant

### 1. Préparer le serveur

```bash
# 1. Créer dossier du projet
mkdir -p ~/api_credit_scoring
cd ~/api_credit_scoring

# 2. Cloner le repository
git clone https://github.com/hefarian/api_credit_scoring.git .

# 3. Créer fichier .env
cat > .env << EOF
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=credit_scoring
DATABASE_URL=postgresql://postgres:postgres@postgres:5435/credit_scoring
EOF

# 4. Démarrer les services
docker compose up -d --build
```

### 2. Accès SSH

**Important:** Le serveur doit accepter les connexions SSH du runner GitHub.

```bash
# Vérifier que SSH fonctionne
ssh user@your-server.com "docker compose version"
```

## Configuration GitHub Secrets

Ajouter les secrets suivants dans GitHub: `Settings > Secrets and variables > Actions`

| Secret | Valeur |
|--------|--------|
| `DEPLOY_HOST` | IP ou domaine du serveur (ex: `192.168.1.100`) |
| `DEPLOY_USER` | Utilisateur SSH (ex: `ubuntu`) |
| `DEPLOY_PRIVATE_KEY` | Clé SSH privée (contenu complet du fichier `.pem` ou `~/.ssh/id_rsa`) |

**Créer une clé SSH (sur le serveur):**

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Puis **copier le contenu de `~/.ssh/deploy_key`** dans le secret GitHub `DEPLOY_PRIVATE_KEY`.

## Workflow d'Intégration Continue/Déploiement

### CI (Intégration Continue) - `.github/workflows/ci.yml`

✅ S'exécute automatiquement à chaque push sur `main` ou `dev`:
- Exécute les tests pytest
- Construit les images Docker

### CD (Déploiement Continu) - `.github/workflows/cd-remote.yml`

✅ S'exécute après CI réussi:
- Se connecte au serveur distant via SSH
- Clone/mise à jour du code
- Redémarrage des containers Docker

## Accès aux Services

Une fois déployé, accédez aux services via:

- **API** : `http://your-server.com:8005`
- **Dashboard Streamlit** : `http://your-server.com:8505`
- **PostgreSQL** : `your-server.com:5435` (user: postgres)

## Monitoring et Logs

**Sur le serveur:**

```bash
# Vérifier les services
docker compose ps

# Voir les logs de l'API
docker compose logs api

# Voir les logs de Streamlit
docker compose logs streamlit

# Redémarrer un service
docker compose restart api
```

## Troubleshooting

### SSH connection refused

```
Error: Connection refused on port 22
```

✓ Vérifier le port SSH (peut ne pas être 22)
✓ Vérifier le firewall du serveur
✓ Vérifier la clé SSH ajoutée dans `authorized_keys`

### Git pull fails

```
Error: Authentication failed for repository
```

✓ Ajouter une deploy key GitHub sur le serveur
✓ Ou utiliser un token GitHub dans l'URL du repo

### Docker compose not found

```
Error: docker-compose: command not found
```

✓ Sur serveur, installer: `sudo apt install docker-compose-plugin`

## Secrets Recommandés (optionnel)

Pour plus de fonctionnalités:

| Secret | Usage |
|--------|-------|
| `SLACK_WEBHOOK` | Notifications Slack après déploiement |
| `DISCORD_WEBHOOK` | Notifications Discord |

Ajouter dans le workflow pour notifier:

```yaml
- name: Notify Slack
  run: curl -X POST ${{ secrets.SLACK_WEBHOOK }} -d 'Deployment complete'
```

---

**Note:** Ce workflow supporte les déploiements sur n'importe quel serveur distant avec SSH, pas limité à VirtualBox.