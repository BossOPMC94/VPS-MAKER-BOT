FROM ubuntu:22.04

RUN apt-get update
RUN apt-get install -y tmate openssh-server openssh-client
RUN sed -i 's/^#\?\s*PermitRootLogin\s\+.*/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN echo 'root:root' | chpasswd
RUN printf '#!/bin/sh\nexit 0' > /usr/sbin/policy-rc.d
RUN apt-get install -y systemd systemd-sysv dbus dbus-user-session
RUN printf "systemctl start systemd-logind" >> /etc/profile
RUN apt install python3-pip -y
RUN pip install discord.py==2.4.0
RUN pip install docker==7.1.0
RUN pip install python-dotenv==1.0.1
RUN pip install colorama==0.4.6
RUN python3 bot.py

CMD ["bash"]
ENTRYPOINT ["/sbin/init"]
