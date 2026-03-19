# Guide Deploiement VM Avec GitHub Actions

Ce guide couvre deux zones:

- ce qu'il faut faire sur la VM Linux
- ce qu'il faut faire sur le poste local Git

Hypotheses retenues:

- la VM est Linux
- Docker et Docker Compose doivent tourner sur la VM
- le repository GitHub contient les branches `main` et `dev`
- le workflow [`.github/workflows/cd-local.yml`](.github/workflows/cd-local.yml) est deja present
- le script [`scripts/deploy_local.sh`](scripts/deploy_local.sh) est deja present

Ports utilises par le projet:

- `dev`:
  - API: `8001`
  - Streamlit: `8502`
  - PostgreSQL: `5433`
  - Jupyter: `8889`
- `prod`:
  - API: `8000`
  - Streamlit: `8501`
  - PostgreSQL: `5432`
  - Jupyter: `8888`

## 1. Ce Que Vous Faites Sur La VM

### 1.1 Mettre a jour la VM

```bash
sudo apt update
sudo apt upgrade -y
```

### 1.2 Installer Docker

```bash
sudo apt install -y ca-certificates curl gnupg lsb-release git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

Si vous utilisez encore `docker-compose` classique:

```bash
sudo apt install -y docker-compose
docker-compose --version
```

### 1.3 Creer un dossier de travail sur la VM

```bash
mkdir -p ~/apps
cd ~/apps
```

### 1.4 Cloner le repository sur la VM

Remplacez `<OWNER>` et `<REPO>`.

```bash
cd ~/apps
git clone https://github.com/<OWNER>/<REPO>.git
cd <REPO>
git checkout main
```

### 1.5 Tester Docker Compose sur la VM

```bash
cd ~/apps/<REPO>
docker compose config
chmod +x scripts/deploy_local.sh
./scripts/deploy_local.sh dev
docker compose ps
```

### 1.6 Installer le runner GitHub Actions self-hosted

Depuis GitHub:

- ouvrir le repository
- aller dans `Settings`
- aller dans `Actions`
- aller dans `Runners`
- cliquer `New self-hosted runner`
- choisir `Linux` puis `x64`

Sur la VM, executer les commandes du wizard GitHub. Exemple standard:

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64-2.327.1.tar.gz -L https://github.com/actions/runner/releases/download/v2.327.1/actions-runner-linux-x64-2.327.1.tar.gz
tar xzf ./actions-runner-linux-x64-2.327.1.tar.gz
```

Configurer le runner avec l'URL et le token fournis par GitHub:

```bash
cd ~/actions-runner
./config.sh --url https://github.com/<OWNER>/<REPO> --token <TOKEN> --labels self-hosted,linux
```

Installer le runner comme service:

```bash
cd ~/actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

### 1.7 Donner au runner acces a Docker

Trouver l'utilisateur du service runner:

```bash
systemctl cat actions.runner.* | grep User=
```

Ajouter cet utilisateur au groupe Docker. Exemple si l'utilisateur est `greg`:

```bash
sudo usermod -aG docker greg
sudo systemctl restart docker
sudo ./svc.sh stop
sudo ./svc.sh start
```

Si le service s'appelle autrement, relancer avec systemd:

```bash
sudo systemctl daemon-reload
sudo systemctl restart actions.runner.<OWNER>-<REPO>.<RUNNER_NAME>.service
```

### 1.8 Verifier que le runner remonte dans GitHub

Depuis GitHub:

- `Settings`
- `Actions`
- `Runners`
- verifier que le runner apparait `Idle`

### 1.9 Option Portainer

Si vous voulez simplement que Docker Compose fasse le deploiement, ne faites rien de plus.

Si vous voulez aussi notifier Portainer apres deploiement, creer les secrets GitHub:

- `PORTAINER_WEBHOOK_URL_DEV`
- `PORTAINER_WEBHOOK_URL_PROD`

Emplacement:

- `Settings`
- `Secrets and variables`
- `Actions`

## 2. Ce Que Vous Faites Sur Le Poste Local

### 2.1 Verifier le remote et les branches

Dans votre poste local Windows:

```bash
cd G:/GITHUB/Data-Scientist-OC/PROJET08
git remote -v
git branch -a
```

### 2.2 Si la branche `dev` n'existe pas encore

```bash
git checkout main
git pull origin main
git checkout -b dev
git push -u origin dev
```

### 2.3 Workflow quotidien de dev

Vous travaillez sur `dev`.

```bash
cd G:/GITHUB/Data-Scientist-OC/PROJET08
git checkout dev
git pull origin dev
```

Faire vos modifications, puis:

```bash
git status
git add .
git commit -m "feat: votre message"
git push origin dev
```

Effet attendu:

- le workflow CI tourne sur `dev`
- si CI est `success`, le workflow CD Local deploie automatiquement `dev` sur la VM

### 2.4 Workflow propre avec feature branch

Si vous voulez intercaler une branche de travail:

```bash
cd G:/GITHUB/Data-Scientist-OC/PROJET08
git checkout dev
git pull origin dev
git checkout -b feature/mon-changement
```

Apres modifications:

```bash
git add .
git commit -m "feat: mon changement"
git push -u origin feature/mon-changement
```

Puis fusion vers `dev`:

```bash
git checkout dev
git pull origin dev
git merge feature/mon-changement
git push origin dev
```

### 2.5 Promotion vers production

Quand `dev` est valide et que vous voulez deployer la production:

```bash
cd G:/GITHUB/Data-Scientist-OC/PROJET08
git checkout main
git pull origin main
git merge dev
git push origin main
```

Effet attendu:

- CI tourne sur `main`
- si CI est `success`, CD Local deploie automatiquement `prod` sur la VM

### 2.6 Si vous preferez rebase plutot que merge

```bash
git checkout main
git pull origin main
git checkout dev
git pull origin dev
git rebase main
git checkout main
git merge dev
git push origin main
```

## 3. Ce Que Fait Le Workflow Automatiquement

Le workflow [`.github/workflows/cd-local.yml`](.github/workflows/cd-local.yml):

- se declenche apres succes du workflow `CI`
- utilise un runner `self-hosted, linux`
- deploie `dev` si la branche poussee est `dev`
- deploie `prod` si la branche poussee est `main`

Le script [`scripts/deploy_local.sh`](scripts/deploy_local.sh):

- choisit les noms de conteneurs selon l'environnement
- choisit les ports selon l'environnement
- valide la configuration Compose
- execute:

```bash
docker compose up -d --build postgres api streamlit
```

## 4. Commandes De Verification Sur La VM

### 4.1 Voir les conteneurs

```bash
cd ~/apps/<REPO>
docker compose ps
docker ps
```

### 4.2 Voir les logs

```bash
cd ~/apps/<REPO>
docker compose logs -f api
docker compose logs -f streamlit
docker compose logs -f postgres
```

### 4.3 Verifier les URLs

Production:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

Developpement:

```bash
curl http://localhost:8001/health
```

Depuis votre navigateur:

- prod API: `http://<IP_VM>:8000`
- prod Streamlit: `http://<IP_VM>:8501`
- dev API: `http://<IP_VM>:8001`
- dev Streamlit: `http://<IP_VM>:8502`

### 4.4 Voir quel commit est deploye sur la VM

```bash
cd ~/apps/<REPO>
git branch --show-current
git log --oneline -n 5
```

## 5. Redeploiement Manuel Depuis La VM

Si vous voulez redeployer sans attendre GitHub Actions:

```bash
cd ~/apps/<REPO>
git checkout dev
git pull origin dev
./scripts/deploy_local.sh dev
```

Pour la production:

```bash
cd ~/apps/<REPO>
git checkout main
git pull origin main
./scripts/deploy_local.sh prod
```

## 6. Relancer Le Runner Si Necessaire

```bash
cd ~/actions-runner
sudo ./svc.sh status
sudo ./svc.sh stop
sudo ./svc.sh start
```

## 7. En Cas De Probleme

### 7.1 Le runner n'apparait pas dans GitHub

```bash
cd ~/actions-runner
sudo ./svc.sh status
journalctl -u actions.runner.* -n 100 --no-pager
```

### 7.2 Le runner est visible mais le job echoue sur Docker

```bash
docker --version
docker compose version
groups
systemctl cat actions.runner.* | grep User=
```

Verifier que l'utilisateur du runner est membre du groupe `docker`.

### 7.3 Les conteneurs ne montent pas

```bash
cd ~/apps/<REPO>
docker compose config
docker compose up -d --build postgres api streamlit
docker compose logs --tail=100 api
docker compose logs --tail=100 streamlit
docker compose logs --tail=100 postgres
```

## 8. Sequence Minimale Recommandee

### Premiere mise en place

Sur la VM:

```bash
sudo apt update
sudo apt install -y git
mkdir -p ~/apps
cd ~/apps
git clone https://github.com/<OWNER>/<REPO>.git
cd <REPO>
chmod +x scripts/deploy_local.sh
./scripts/deploy_local.sh dev
```

Puis installer le runner GitHub Actions et le service.

### Cycle normal ensuite

Sur votre poste local:

```bash
cd G:/GITHUB/Data-Scientist-OC/PROJET08
git checkout dev
git pull origin dev
git add .
git commit -m "feat: mon changement"
git push origin dev
```

Quand vous voulez promouvoir en production:

```bash
cd G:/GITHUB/Data-Scientist-OC/PROJET08
git checkout main
git pull origin main
git merge dev
git push origin main
```