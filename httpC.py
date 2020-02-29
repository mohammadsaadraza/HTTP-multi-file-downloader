import argparse
import socket
import sys
import select
import math
import threading
import os
import json
import time
import schedule

def define_args():
    ag = argparse.ArgumentParser()
    ag.add_argument("-nf", nargs=1,required=True, help="No. of files")
    ag.add_argument("-n", nargs=1,required=True, help="Total number of simultaneous connections")
    ag.add_argument("-i", nargs=1,required=True, help="Time interval in seconds between metric reporting")
    ag.add_argument("-f", nargs='+',required=True, help="Address pointing to the file locations on the web")
    ag.add_argument("-o", nargs='+',required=True, help="Address pointing to the locations where the files are downloaded")
    ag.add_argument("-r", nargs='?',help="Whether to resume the existing download in progress")

    arguments=vars(ag.parse_args())
    return arguments

def is_non_zero_file(fpath):  
    return os.path.isfile(fpath) and os.path.getsize(fpath) > 0

def progressBar():
    for file in fileProgress:
        print( file + ": " + str(fileProgress[file][0]) + "/" + str(fileProgress[file][1]) + " bytes, download speed " + str(fileProgress[file][2]) + " Kb/s")
    #print(fileProgress)
    print("")

def pending():
    #print(isPending)
    while isPending:
        schedule.run_pending()

def parseURL(a):
    url = a[ a.find("//")+2 : a.find("/",a.find("//")+2)]
    file = a[ a.find("/",a.find("//")+2) : ]
    extension = a[a.rfind("."):]
    return url,file,extension

def define_requirements(arguments):
    num_files = arguments['nf'][0]
    num_connections = arguments['n'][0]
    time_interval = arguments['i'][0]
    filenames = arguments['f']
    resume = arguments['r']
    output_location = arguments['o'][0]

    return num_files,num_connections,time_interval, filenames,resume, output_location

def get_info(fileURL,port):
    url,file,extension = parseURL(fileURL)
    host_ip = socket.gethostbyname(url)
    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.connect((host_ip,port))
    sock.sendall(("HEAD "+file + " HTTP/1.0\r\nHOST: " + url + "\r\n\r\n").encode())

    response = sock.recv(1024)
    while select.select([sock],[],[],3)[0]:
        data = sock.recv(1024)
        if not data: break
        response += data
    sock.close()

    #print(response)
    a_range = response[response.find("Accept-Ranges: ".encode()) + 15 : response.find("\r".encode(),response.find("Accept-Ranges: ".encode()))].decode()
    c_length = response[response.find("Content-Length: ".encode()) + 16 : response.find("\r".encode(),response.find("Content-Length: ".encode()))].decode()
    code = response[9 : 13].decode()

    if a_range != "bytes":
        a_range = None
    if not c_length.isdigit():
        c_length = None
        
    return a_range,c_length,code
    
def start_connection(fileURL, port, conn_id, bytes_start,bytes_end,file_pieces, accept_ranges,resume_download):
    if bytes_start<bytes_end:
        #print("jfnjf")
        url,file,extension = parseURL(fileURL)
        host_ip = socket.gethostbyname(url)

        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.connect((host_ip,port))
        if accept_ranges is None:
            sock.sendall(("GET "+file + " HTTP/1.0\r\nHOST: " + url + "\r\n\r\n").encode())
        else:
            sock.sendall(("GET "+file + " HTTP/1.0\r\nHOST: " + url + "\r\nRange: bytes=" + str(bytes_start) + "-" + str(bytes_end) + "\r\n\r\n").encode())

        response = b''
        
        while  select.select([sock],[],[],7)[0]:
            data = sock.recv(2048)
            if not data: break
            response += data
            fileProgress[file][0] += sys.getsizeof(data)
            if fileProgress[file][0] >= fileProgress[file][1]:
                fileProgress[file][0] = fileProgress[file][1]

            fileProgress[file][2] = (fileProgress[file][1]/(time.time()-fileProgress[file][3]))/1024
        
        sock.close()

        response = response[response.find("\r\n\r\n".encode())+4:]
        #print(sys.getsizeof(response))
        if resume_download:
            path = file["z" + file.rfind("/")+1:file.rfind(".")] + "_" + str(conn_id)+ extension
        else:
            path = file[file.rfind("/")+1:file.rfind(".")] + "_" + str(conn_id)+ extension
        file_pieces.append(path)
        with open( path,"wb")as s:
            s.write(response)
            s.close()
        
        
        #print(response)

def file_thread(fileProgress, fileURL, port, num_connections, content_length, accept_ranges,resume_download ,output_location):
    
    print('FILEEEE: ', fileURL)

    url,file,extension = parseURL(fileURL)
    bytes_interval = math.ceil(content_length/num_connections)-1
    bytes_start = 0
    bytes_end = bytes_start + bytes_interval

    file_pieces=list()
    threads = list()
    error = False

    fileProgress[file] = [bytes_start,content_length,0.0,time.time()]

    if accept_ranges is None:
        num_connections = 1
        bytes_end = content_length -1

    if resume_download:
        if is_non_zero_file("resume.json"):
            with open("resume.json") as j:
                resume = json.load(j)
                bytes_start = resume[fileURL]
                bytes_end = bytes_start + bytes_interval
                file_pieces = resume[fileURL][1]
    else:
        resume = {}
        
    for i in range(num_connections):
  
        try:
            thread = threading.Thread(target=start_connection , args = (fileURL, port, i, bytes_start, bytes_end, file_pieces,accept_ranges, resume_download))
            thread.start()
            threads.append(thread)
        except:
            print("Error with " + fileURL)
            error = True
            with open('resume.json', 'w') as outfile:  
                json.dump(resume, outfile)
            break
        
        resume[fileURL] = [bytes_start,file_pieces]
        with open('resume.json', 'w') as outfile:  
            json.dump(resume, outfile)
            
        bytes_start = bytes_end +1
        bytes_end = bytes_start + bytes_interval
        
    if not error:
        
        for x in threads:
            x.join()

        del resume[fileURL]
        with open('resume.json', 'w') as outfile:  
            json.dump(resume, outfile)

        file_pieces.sort()
        out_file = file[file.rfind("/")+1:file.rfind(".")] + extension

        if not os.path.exists(output_location):
            os.makedirs(output_location)
        
        with open(output_location + "/" + out_file, "wb") as outfile:
            for fname in file_pieces:
                with open(fname, "rb") as infile:
                    for line in infile:
                        outfile.write(line)
                os.remove(fname)
                
        
num_files,num_connections,time_interval, filenames,resume, output_location = define_requirements( define_args())
PORT = 80
fileProgress = {}

if resume is None:
    resume = False
else:
    resume = True

schedule.every(float(time_interval)).seconds.do(progressBar)
isPending = True
threading.Thread(target=pending).start()
    
for fileURL in filenames:
    url, file, extension = parseURL(fileURL)
    if url.find(":") != -1:
        PORT = url[ url.find(":") + 1 : ]
        url = url[ : url.find(":")]

    accept_ranges , content_length,code = get_info(fileURL,PORT)
    threads = list()
    
    if (not content_length is None) and (int(content_length) > 0) and (int(code) == 200) :
        content_length = int(content_length)
        
        try:
            
            thread = threading.Thread(target=file_thread , args=(fileProgress, fileURL, PORT, int(num_connections),content_length,accept_ranges,resume, output_location))
            thread.start()
            threads.append(thread)
        except:
            print("Outer Error with " + fileURL)
            
        
        for x in threads:
            x.join()

        print("DONE " + fileURL)
        #isPending= False
        #schedule.cancel_job(progressBar)
    else:
        print("Can't download file; Code "+ code+ " " + fileURL)



                                      
    
    

