# GitHub release checklist

Tarman Studio is designed to be published from `Tihulu/tarman-studio`.

## First push

```bash
gh auth login
gh repo create Tihulu/tarman-studio --public --source=. --remote=origin --push
```

If you already created the repository in the browser:

```bash
git init
git add .
git commit -m "Initial GPL release of Tarman Studio"
git branch -M main
git remote add origin git@github.com:Tihulu/tarman-studio.git
git push -u origin main
```

## Create a release

```bash
git tag v0.4.0
git push origin v0.4.0
```

The GitHub Actions workflow builds:

- source `.tar.gz`
- source `.zip`
- `Tarman_Studio-<version>-x86_64.AppImage`

and attaches them to the GitHub Release.

## One-line install command

After the repository is public:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tarman-studio/main/install-online.sh | bash
```

Force AppImage mode:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tarman-studio/main/install-online.sh | TARMAN_INSTALL_MODE=appimage bash
```

Force pyenv/source mode, which also installs the CLI:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tarman-studio/main/install-online.sh | TARMAN_INSTALL_MODE=pyenv bash
```
