# Guide to install and run server on  Ubuntu VM

Note: 
	Python 3.8 version required.

Step 1:
	Install mininet:
		>>> git clone https://github.com/mininet/mininet
		>>> cd mininet
		>>> git tag  # list available versions
		>>> git checkout -b mininet-2.3.0 2.3.0  # or whatever version you wish to install
		>>> cd ..
		>>> mininet/util/install.sh -a
		>>> Test Purpose: sudo mn --switch ovsbr --test pingall


Step 2: Get server code
        1. Get server code from https://github.com/Si11-ibrahim/Network-Simulator-Server.git


Step 3: Virtual Environment
		>>> sudo apt update && sudo apt upgrade 
		
		Downgrade python: 
			>>> sudo apt update
			>>> sudo apt install python3.8 python3.8-venv python3.8-dev -y

		>>> sudo apt install python3-pip (Install if pip3 not working)
		>>> sudo pip3 install virtualenv
	
	Create new venv:
		>>> virtualenv <new-env-name>
	
	To activate: 
		>>> source <venv name>/bin/activate

Step 4: Install required packages

	Note: Must activate venv before the installation.

	Install required packages for server:
		>>> pip install uvicorn
		>>> pip install "fastapi[standard]"
		>>> pip install mininet
		>>> pip install ryu

Step 5: Pox controller
	Installation:
		>>> git clone https://github.com/noxrepo/pox.git
	
	Get "packet_tracker.py" from Network-Simulator-Server/controller directory and put it in pox/ext (Cloned pox repository) directory
	
	Note: Run this controller in another ubuntu instance.

	To run the controller:
		>>> ./pox.py forwarding.l2_learning packet_tracker

Step 5: RYU Controller
	Installation:
		Inside venv,
		>>> pip install ryu
		>>> pip install --upgrade pip wheel setuptools
		>>> pip3 install setuptools==58.2.0
		>>> pip install eventlet==0.30.2

		>>> ryu-manager --version (Verification)

	

	Usage:
		Inside the controller.py located directory,

		>>> ryu-manager controller.py


Final steps to run server:
	1. >>> sudo su
	2. activate venv 
	3. run pox
	4. Make sure you are inside server directory
	5. To start server: python3 -m uvicorn main:app --reload

Error handling:
	While running mininet:
		If mininet stuck at starting switches:
			>>> sudo ovs-vswitchd --pidfile --detach

		If "address already in use" error at the time of starting server:
			>>> sudo lsof -t -i tcp:8000 | xargs kill -9

	While Installing ryu:
		Gunicorn importError: 'ALREADY_HANDLED' 
		 >>> pip install eventlet==0.30.2

