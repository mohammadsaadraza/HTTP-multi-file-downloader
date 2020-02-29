import socket,select
def parseURL(a):
    url = a[ a.find("//")+2 : a.find("/",a.find("//")+2)]
    file = a[ a.find("/",a.find("//")+2) : ]
    extension = a[a.rfind("."):]
    return url,file,extension
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

    print(response)
    a_range = response[response.find("Accept-Ranges: ".encode()) + 15 : response.find("\r".encode(),response.find("Accept-Ranges: ".encode()))].decode()
    c_length = response[response.find("Content-Length: ".encode()) + 16 : response.find("\r".encode(),response.find("Content-Length: ".encode()))].decode()

    if a_range != "bytes":
        a_range = None
    if not c_length.isdigit():
        c_length = None
        
    return a_range,c_length

print(get_info("https://images-na.ssl-images-amazon.com/images/I/81RZ9UmZP3L._SX425_.jpg",80))
