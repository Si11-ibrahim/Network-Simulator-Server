### Guide to install and run server on WSL2

Step 1:
	Install mininet:
		>>> git clone https://github.com/mininet/mininet
		>>> cd mininet
		>>> git tag  # list available versions
		>>> git checkout -b mininet-2.3.0 2.3.0  # or whatever version you wish to install
		>>> cd ..
		>>> mininet/util/install.sh -a
		>>> Test Purpose: sudo mn --switch ovsbr --test pingall

Step 2: Install virtual environment

		>>> sudo apt update && sudo apt upgrade 
		>>> sudo apt install python3-pip (Install if pip3 not working)		
		>>> sudo pip3 install virtualenv
	
	Create new venv:
		>>> virtualenv <new-env-name>
	
	To activate: 
		>>> source <venv name>/bin/activate

Step 3: Installing required packages

	Note: Must activate venv before installation.

	Install required packages for server:
		>>> pip install uvicorn
		>>> pip install "fastapi[standard]"
		>>> pip install mininet
		
Step 4: Copy server codes
	1. Copy server codes located in server directory
	2. Create a directory called server inside ubuntu
	3. Paste the codes as same structure as where you copied


Step 5:
	Install pox controller:
		>>> git clone https://github.com/noxrepo/pox.git
	
	Note: Run this controller in another ubuntu instance.

	To run the controller:
		>>> ./pox.py forwarding.l2_learning

Final steps to run server:
	1. >>> sudo su
	2. activate venv 
	3. run pox
	4. Make sure you are inside server directory
	5. To start server: python3 -m uvicorn main:app --reload

Error handling: 
	If mininet stuck in starting switches, run:
		>>> sudo ovs-vswitchd --pidfile --detach





