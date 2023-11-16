# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"

  # Speed up operations by using rsync rather than the default VirtualBox shared folder.
  # This requires manual running of `vagrant rsync-auto` for updates to be reflected on
  # the guest.
  # Despite the suggestion in the docs to exclude the .git/ folder, it is included to
  # enable working with pre-commit on the machine.
  # TODO: the problem with running pre-commit on the machine is that it requires syncing
  # TODO: files back -- might be better to add .git/ to the ignored dirs and just run
  # TODO: pre-commit on the host, which is relatively low risk
  # TODO: alternatively, can explore other two-way sync options like NFS and VMWare
  config.vm.synced_folder ".", "/vagrant",
   type: "rsync",
   rsync__exclude: [".coverage", ".mypy_cache/", ".pytest_cache/", ".ruff_cache/", "__pycache__/", "data/", "htmlcov/"]

  config.vm.provider "virtualbox" do |vb|
    vb.memory = "4096"
  end

  config.vm.network "forwarded_port", guest: 8888, host: 8888, host_ip: "127.0.0.1"

  config.vm.provision "shell", name: "apt dependencies", inline: <<-SHELL
    apt-get update
    apt-get install -y pipx
  SHELL

  config.vm.provision "shell", name: "poetry", privileged: false, inline: <<-SHELL
    pipx install poetry==$(cat /vagrant/.poetry-version)
  SHELL

  config.vm.provision "shell", name: "python dependencies", privileged: false, inline: <<-SHELL
    set -e
    cd /vagrant
    poetry install
    poetry run pre-commit install
    echo "Running the CLI to verify everything works"
    poetry run rls-data --help
  SHELL

  config.vm.provision "shell", name: "apt-upgrade", run: "always", inline: <<-SHELL
    apt-get update && apt-get upgrade -y
  SHELL
end
