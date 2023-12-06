import paramiko
import time

hostname = "10.52.54.106"
port = 5122
user = "root"
passwd = "ALu12#"

try:
    client = paramiko.SSHClient()		# create paramiko SSH object client
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
    client.connect(hostname, port, username=user, password=passwd) # connect function
    while True:					# infinite loop to ask for an input
        try:
            cmd = input("$>")			# input function
            if cmd == "exit":break		# exit while loop
            stdin, stdout, stderr = client.exec_command(cmd)
            
            print(stdout.read().decode())
                
        
        except KeyboardInterrupt:
            break
    client.close()				# close the connection to the NE
except Exception as err:
    print(str(err))