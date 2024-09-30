FROM ubuntu:22.04

RUN apt-get update
RUN apt-get install -y tmate openssh-server openssh-client
RUN sed -i 's/^#\?\s*PermitRootLogin\s\+.*/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN echo 'root:root' | chpasswd
RUN printf '#!/bin/sh\nexit 0' > /usr/sbin/policy-rc.d
RUN apt-get install -y systemd systemd-sysv dbus dbus-user-session
RUN printf "systemctl start systemd-logind" >> /etc/profile
RUN apt install curl -y
RUN apt install ufw -y && ufw allow 80 && ufw allow 443 && apt install net-tools -y
RUN apt-get update && apt-get install -y \
    iproute2 \
    hostname \
    && rm -rf /var/lib/apt/lists/*
RUN echo "crashcloud" > /etc/hostname
RUN echo "127.0.0.1 crashcloud" >> /etc/hosts


CMD ["bash"]
ENTRYPOINT ["/sbin/init"]
