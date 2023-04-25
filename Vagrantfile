# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"

  config.vm.provider "virtualbox" do |vb|
    vb.memory = "4096"
  end

  config.vm.network "forwarded_port", guest: 8888, host: 8888, host_ip: "127.0.0.1"

  config.vm.provision "shell", name: "apt dependencies", inline: <<-SHELL
    apt-get update
    apt-get install -y pipx
  SHELL

  config.vm.provision "shell", name: "poetry", privileged: false, inline: <<-SHELL
    pipx install poetry==1.4.2
  SHELL

  config.vm.provision "shell", name: "python dependencies", privileged: false, inline: <<-SHELL
    set -e
    cd /vagrant
    poetry install
    poetry run pre-commit install
    echo "Running the CLI to verify everything works"
    poetry run rls-data --help
  SHELL
end
