# Packaging

This repo ships a standalone Fedora desktop app and includes local, CI, and COPR-friendly packaging.

## Local RPM build

Build:

```bash
./scripts/build-rpm.sh
```

Install newest local RPM:

```bash
./scripts/install-rpm.sh
```

The RPM installs:

- the launcher entry: `/usr/share/applications/hwremote-monitor.desktop`
- hicolor app icons: `/usr/share/icons/hicolor/*/apps/hwremote-monitor.png`
- runtime window icon assets: `/usr/share/hwmonitor-remote/assets/icons/`

Uninstall:

```bash
./scripts/uninstall-rpm.sh
```

## Branding assets

The branded app icon is generated from the repository root `logo.png`.

- source image: `logo.png`
- runtime icon files used by the standalone app: `assets/icons/`
- packaged Linux desktop icon sizes: `packaging/linux/icons/hicolor/`

## GitHub Actions

Workflow file:

```text
.github/workflows/build-rpm.yml
```

It builds:

- source tarball
- SRPM
- noarch RPM

and uploads them as GitHub Actions artifacts.

## COPR

The spec file is already suitable for COPR source package builds:

```text
packaging/rpm/hwmonitor-remote.spec
```

Typical COPR flow:

1. Create a COPR project.
2. Upload the SRPM built by `./scripts/build-rpm.sh`.
3. Or connect the GitHub repo and use the spec file directly.

Expected BuildRequires are minimal because this package is Python + data files only.
