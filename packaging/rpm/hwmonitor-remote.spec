Name:           hwmonitor-remote
Version:        0.3.2
Release:        1%{?dist}
Summary:        Standalone desktop app for remote Windows hardware monitoring

License:        GPL-3.0-or-later
URL:            https://github.com/multidraxter-bit/hwmonitor-remote
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3
Requires:       python3-tkinter
Requires:       openssh-clients

%description
HWMonitor Remote is a standalone desktop app for Fedora that monitors
detailed Windows hardware sensors over SSH or HTTP using LibreHardwareMonitor
data and helper scripts.

%prep
%autosetup

%build

%install
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_datadir}/%{name}/assets/icons
install -d %{buildroot}%{_datadir}/%{name}/fedora
install -d %{buildroot}%{_datadir}/%{name}/windows
install -d %{buildroot}%{_datadir}/applications
for size in 16 22 24 32 48 64 128 256 512; do \
  install -d %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps; \
done
install -d %{buildroot}%{_docdir}/%{name}

install -m 0644 README.md %{buildroot}%{_docdir}/%{name}/README.md
install -m 0644 assets/icons/hwremote-monitor.png %{buildroot}%{_datadir}/%{name}/assets/icons/hwremote-monitor.png
install -m 0644 assets/icons/hwremote-monitor.ico %{buildroot}%{_datadir}/%{name}/assets/icons/hwremote-monitor.ico
install -m 0644 fedora/fetch_snapshot.py %{buildroot}%{_datadir}/%{name}/fedora/fetch_snapshot.py
install -m 0755 fedora/hwmonitor_remote.py %{buildroot}%{_datadir}/%{name}/fedora/hwmonitor_remote.py
install -m 0644 windows/lhm-snapshot.ps1 %{buildroot}%{_datadir}/%{name}/windows/lhm-snapshot.ps1
install -m 0644 windows/lhm-exporter.ps1 %{buildroot}%{_datadir}/%{name}/windows/lhm-exporter.ps1
install -m 0644 windows/install-exporter.ps1 %{buildroot}%{_datadir}/%{name}/windows/install-exporter.ps1
install -m 0644 packaging/linux/hwremote-monitor.desktop %{buildroot}%{_datadir}/applications/hwremote-monitor.desktop
for size in 16 22 24 32 48 64 128 256 512; do \
  install -m 0644 packaging/linux/icons/hicolor/${size}x${size}/apps/hwremote-monitor.png %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/hwremote-monitor.png; \
done

cat > %{buildroot}%{_bindir}/hwremote-monitor <<'EOF'
#!/usr/bin/bash
exec python3 /usr/share/hwmonitor-remote/fedora/hwmonitor_remote.py "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/hwremote-monitor

%files
%doc %{_docdir}/%{name}/README.md
%{_bindir}/hwremote-monitor
%{_datadir}/applications/hwremote-monitor.desktop
%{_datadir}/%{name}/assets/icons/hwremote-monitor.png
%{_datadir}/%{name}/assets/icons/hwremote-monitor.ico
%{_datadir}/%{name}/fedora/fetch_snapshot.py
%{_datadir}/%{name}/fedora/hwmonitor_remote.py
%{_datadir}/%{name}/windows/lhm-snapshot.ps1
%{_datadir}/%{name}/windows/lhm-exporter.ps1
%{_datadir}/%{name}/windows/install-exporter.ps1
%{_datadir}/icons/hicolor/16x16/apps/hwremote-monitor.png
%{_datadir}/icons/hicolor/22x22/apps/hwremote-monitor.png
%{_datadir}/icons/hicolor/24x24/apps/hwremote-monitor.png
%{_datadir}/icons/hicolor/32x32/apps/hwremote-monitor.png
%{_datadir}/icons/hicolor/48x48/apps/hwremote-monitor.png
%{_datadir}/icons/hicolor/64x64/apps/hwremote-monitor.png
%{_datadir}/icons/hicolor/128x128/apps/hwremote-monitor.png
%{_datadir}/icons/hicolor/256x256/apps/hwremote-monitor.png
%{_datadir}/icons/hicolor/512x512/apps/hwremote-monitor.png

%changelog
* Fri Mar 06 2026 Loofi <loofi@loofi.com> - 0.3.1-1
- Polish desktop UX, add merged-source browsing improvements, and ship end-user guide screenshots

* Fri Mar 06 2026 Loofi <loofi@loofi.com> - 0.3.0-1
- Improve standalone desktop app UI, sensor pinning, filters, trends, keyboard actions, and branding icon

* Fri Mar 06 2026 Loofi <loofi@loofi.com> - 0.2.0-1
- Package standalone desktop app as an RPM
