"""
#########################################################################
#    ARM PROGRAM TECHNICAL REVIEW
#    Reviewed by:
#    Date:
#########################################################################
#
# Job name:        FPDS Download
# Program name:    fpds_dl.py
# Programmer:      Andrew Banister; customized for Windows 7 Towers by Rob Letzler

Downloads all zip files from the Federal Procurement Data System for a particular fiscal year or year range

This version must be run directly on a GAO Windows 7 tower; or another image with a copy of PKZip in 
C:\progra~1\PKWARE\PKZIPC\pkzipc.exe
because 1) very large ZIP files tend to be slightly invalid in ways that Python's ZIP library cannot
handle, but PKZip can and 2) we have been requested to not run major downloads on VDI.

There is another version of this code that can be run directly on a GAO Windows 7 thin client
laptop with Ancaconda Python installed, but that version requires the user to execute batch
files in VDI to finish the unzipping process

Each year the Federal Procurement Data System puts out one ZIP file for each agency.  
This program downloads all of the ZIP files, unzips them, combines them into a single consolidated ZIP
and records what it did in a LOG file.
The user selects a base directory to contain FPDS downloads using a graphical dialog box.  
The program then creates annual subdirectories within this base directory.


The user specifies the year(s) requested and an execution delay in the console.  
The execution delay allows the user to launch a job at any time that will run overnight, 
when it will not be competing with as many other GAO or FDPS users

This program sometimes stalls after downloading about 1.5 years of data, presumably
because the FPDS server is throttling its bandwidth

##########################################################################
"""

#import string and download libraries
import zipfile, shutil, errno, hashlib, subprocess, os, requests, sys, tkinter, re, time
from tkinter import filedialog
from datetime import datetime
#import audit trail library
import trace


#this assertion suffices to prevent execution on VDI
assert os.path.isfile(r"C:\progra~1\PKWARE\PKZIPC\pkzipc.exe"), "The required PK ZIP program, PKZipC.exe, was not found in C:\\progra~1\\PKWARE\\PKZIPC\\!  This program requires that executable; and must be run on a computer with it -- such as a GAO windows 7 tower."

#set the directory to the path containing this script; doing so allows the tracing to work.
#otherwise you get errno 2; see: http://stackoverflow.com/questions/15725273/python-oserror-errno-2-no-such-file-or-directory
#Setup tkinter to create filedirectory box
root = tkinter.Tk()
root.withdraw()
user_path = filedialog.askdirectory()
os.chdir(user_path)

# create a Trace object -- which will create a log file that counts the number of executions of each line below.
tracer = trace.Trace(
     #the goal of this line -- which comes straight from the sample code -- is to generate trace files only for GAO-written code and not more than a dozen trace files for Python-supplied code
     ignoredirs=[sys.prefix],
     #, sys.exec_prefix],
     trace=0,
     count=1)

def dtime(path=""):
    """Gets current time or date modified time.
    
    If no path is provided, returns current time. If path is provided, returns time the file was modified.
    
    Arg:
            path: The path of the file you want to get the date modified.
    Returns:
            Current time or date modified time in the format 'mm/dd/yyyy H:M:S AM/PM'.
    """
    if path=="":
        return (datetime.now().strftime('%m/%d/%Y %I:%M:%S %p'))
    else:
        return (datetime.fromtimestamp(int(os.stat(path).st_mtime)).strftime('%m/%d/%Y %I:%M:%S %p'))

def find_id(html_string, logfile):
    """Obtains agency IDs to be used for scraping FPDS zip files.

    This pulls out all elements called "id" and writes them to an array
    by using regular expresions (it takes everything between 'id="4' and '">').

    Arg:
            html_string: A string of html from the FPDS direcotry for a particular Fiscal Year.
    Returns:
            A list of agency IDs to be used in creating zipfile urls.
    """

    IDs = re.findall("id=\"4(.*?)\">",html_string)
    foldergifs = re.findall("images/folder.gif",html_string)
    #check to see if the regular expression captured all of the IDs
    if len(IDs) != len(foldergifs): #if the # of IDs found does not match the number of folder.gif pictures
         logfile.write('All IDs not found. Check html directory. Found %s IDs and %s foldergifs' % (len(IDs), len(foldergifs)))
         print('All IDs not found. Check html directory. Found %s IDs and %s foldergifs' % (len(IDs), len(foldergifs)))
    return IDs


def fpds_dl(year, PATH):
    """Downloads all FPDS data for a particular Fiscal Year.

    This builds URLs for each agency's zip file, then downloads and unzips the files under 50mb.
    Files greater than 50mb must be unzipped with PKZip by running the batch file in VDI.
    An html of the directory is downloaded. A log file is created containing: 
    Time script ran, a check that the zip files contain an IDV and AWARD file, file sizes, file date times, 
    and an md5 hash of the zip content.

    Arg:
            year: The Fiscal Year you want to download.
    Returns:
            Nothing. Saves files.
    """
    #setup logfile
    print (PATH)
    logfile = open(os.path.join(PATH, "FPDS_DL_log_file.log"),'w')
    logfile.write("[%s] fpds_dl.py began run\n" % dtime())

    yy = str(year)[-2:]
    #get url from main directory to use to pull the agency IDs
    #FY16 directory is formatted different from other years it seprates with a _ instead of a -
    #This pulls the folder name directly from the home directory with all years using regex
    directory_all = requests.get("https://www.fpds.gov/ddps/directory_browser/index.php?somepath=")
    directory_year = re.findall("a href=\"(.*?)\">",directory_all.text)
    #From the list of directory links, find the directory for the input year
    regex = re.compile(".*(%s).*" % yy)
    directory_end = [m.group(0) for l in directory_year for m in [regex.search(l)] if m][0]
    #example: https://www.fpds.gov/ddps/directory_browser/index.php?somepath=..%2FFY13-V1.4&n=2
    directory_url = "https://www.fpds.gov/ddps/directory_browser/index.php%s" % directory_end
    #prefix and suffix we use to build the urls for the zip files
    prefend = re.findall("%2(.*?)&n=2",directory_end)[0][1:]
    pref = "https://www.fpds.gov/ddps/%s/" % prefend
    if 2003 < year < 2015:
        suf = "-DEPTOctober" + str(year-1) + "-Archive.zip"
        #after 2015, the suffix is different
    elif 2015<= year <= datetime.now().year:
        suf = "-DEPT-1001" + str(year-1) + "TO0930" + str(year) + "-Archive.zip"
    else:
        logfile.write('%s Year out of bounds\n' % year)
        raise ValueError('%s Year out of bounds' % year)

    # Download directory_url
    f = requests.get(directory_url, stream = True)
    # Save directory
    path_directory = os.path.join(PATH, "FPDS_directory_FY%s.html" % year)
    with open(path_directory, "w") as directory:
        directory.write(f.text)
        logfile.write("[%s] Saved directory of FPDS for FY %s\n" %(dtime(), year))
        logfile.write("Filename: %s %s bytes.\n" % (path_directory, os.stat(path_directory)))
    #Get zipfile links of agency IDs
    links = find_id(f.text, logfile)
    logfile.write("Agency IDs obtained: %r\n" % links)
    logfile.write("Zip urls attempted to downloaded:\n")
    # Download files and unzip
    #links2 = links[0:3] #Tests subset of file
    # create urls
    zip_urls=[]
    for l in links: #Change to links to dl all
        if l == 'OTHER_DOD_AGENCIES': #special case for OTHER DOD. Second ID is DOD-OTHER_DOD
            u = pref + l + "/DOD-OTHER_DOD" + suf
        else:
            u = pref + l + "/" + l + suf #url contains the agency ID twice
        zip_urls.append(u)
        logfile.write(u+"\n")
    counter = 0 #initialize counter that checks if all identified files were downloaded
    if len(zip_urls) != len(links):
        logfile.write("ERROR: Missing some zip urls\n")
    for u in zip_urls:
        try:
            request = requests.get(u, stream=True)
        except requests.exceptions.RequestException as e:
            logfile.write("Can't retrieve %s: %s\n" % (u, e))
            print("Can't retrieve %s: %s" % (u, e))
        try:
            request = requests.get(u, stream=True)
        except requests.exceptions.RequestException as e:
            logfile.write("Can't retrieve %s: %s\n" % (u, e))
            print("Can't retrieve %s: %s" % (u, e))
        if request.status_code == 200:
            counter+= 1
        else:
            logfile.write("%s Can't retrieve %s\n" % (request.status_code, u))
            print("%s Can't retrieve %s" % (request.status_code, u))
        fname = re.search("([^/]+$)",u).group(0)
        file_name_and_path = os.path.join(PATH, fname)
        try:
            # Initilize md5 hash key
            hash_md5 = hashlib.md5()
            hash_all_updated = True
            with open(file_name_and_path, "wb+") as zip_file:
                # Write the contents of the downloaded file chunk by chunk into the new file
                for chunk in request.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        zip_file.write(chunk)
                        #add data to hash key
                        try:
                            hash_md5.update(chunk)
                        except:
                            hash_all_updated = False
            #if every chunk was captured in the hash output the hash key
            if hash_all_updated:
                hash_text = " md5: %s" % hash_md5.hexdigest()
            else: hash_text = "hash not updated succesfully"
            #record information about the file we are currently reading
            logfile.write("[%s] Saved %s\t%s bytes. %s\n" % (dtime(file_name_and_path), fname, os.stat(file_name_and_path).st_size, hash_text))
        except:
            logfile.write("File %s not saved\n" % u)
        
        #open recently downloaded zip file
        with open(file_name_and_path, 'rb') as fileobj:
            try:
                filezip = zipfile.ZipFile(fileobj, allowZip64=True)
                idv = False
                award = False
                for member in filezip.infolist():
                    #check IDV files and AWARD files exist in the zip file
                    if re.search("-[^-]*.xml$",member.filename).group(0) == "-IDV.xml": idv=True
                    if re.search("-[^-]*.xml$",member.filename).group(0) == "-AWARD.xml": award=True
                                        #Log missing file (IDV or AWARD)
                    if not (idv and award):
                        logfile.write("Missing %s %s for %s\n" % ("IDV.xml"*idv, "AWARD.xml"*award, fname))

                    #only unzip the current member with Python if the ZIP file is small enough that Python should work
                    if os.stat(file_name_and_path).st_size < 50000000:  #if zip file size less than 50mb, handle in python
                        try:
                            target_path = os.path.join(PATH, member.filename)
                            if target_path.endswith('/'):  # folder entry, create
                                try:
                                    os.makedirs(target_path)
                                except (OSError, IOError) as err:
                                    # Ignore Windows error if the folders already exist
                                    if err.errno != errno.EEXIST:
                                        raise
                                continue
                            with open(target_path, 'wb') as outfile, filezip.open(member) as infile:
                                shutil.copyfileobj(infile, outfile)
                            #Preserve file modified time by manually changing it
                            date_time = time.mktime(member.date_time + (0, 0, -1))
                            os.utime(target_path, (date_time, date_time))
                            file_time = datetime(*member.date_time).strftime('%Y-%m-%d %H:%M:%S')
                            #Log file name, file size, and file modified time, for files unzipped
                            logfile.write("%s %s bytes.\tDate modified: %s\n" % (member.filename, member.file_size, file_time))
                        except zipfile.error as e:
                            logfile.write('%s did not unzip correctly.: %s\n' % (member, e))
                #if zip file size greater than or equal to 50mb, shell out to PKZIP to extract everything in one operation
                #we do so outside the loop.
                if os.stat(file_name_and_path).st_size >= 50000000:  
                #logfile.write("File %s too large. Run Batch file to unzip with PKZip.\n" % file_name_and_path)
                #extract_batch_file.write("C:\\progra~1\\PKWARE\\PKZIPC\\pkzipc.exe -extract %s\n" % file_name_and_path)
                #contains_batch = True
                #THIS CODE BLOCK DOES NOT WORK ON VDI BECAUSE OUR PKZIP LICENSE DOES NOT
                #ALLOW "SERVER" INSTALLATIONS, AND APPARENTLY CALLING IT FROM CITRIX LOOKS LIKE A SERVER INSTALLATION TO IT
                #on VDI, it throws the following exception:
                # 253
                #['pkzipc.exe', '-extract', '4100-MERITSYSTEMSPROTECTIONBOARD.zip']
                #b'PKZIP(R)  Version 14 ZIP Compression Utility for Windows Evaluation Version \r\nPortions copyright (C) 1989-2014 PKWARE, Inc.  All Rights Reserved. \r\nReg. U.S. Pat. and Tm. Off.  Patent No.
                # 5,051,745  7,793,099  7,844,579  \r\n7,890,465  7,895,434;  Other patents pending\r\n\r\n\r\n\r\nPKZIP: (E253) This program is not licensed for use on Windows Server platforms.\r\nPlease contact
                #PKWARE to obtain an appropriate server product for this machine.\r\n'
                    subprocess_results= ""
                    try:
                        #change directory so that the unzipped files land in the right place
                        os.chdir(PATH)                        
                        subprocess_results = subprocess.check_output([r"C:\progra~1\PKWARE\PKZIPC\pkzipc.exe","-extract", file_name_and_path],  stderr=subprocess.STDOUT)
                        logfile.write(repr(subprocess_results)+"\n")
                        #out of an abundance of caution, reset the working directory to what it has traditionally been for
                        #all the program execution
                        os.chdir(user_path)
                    except CalledProcessError as e:
                        print(repr(e.returncode))
                        print(repr(e.cmd))
                        print(repr(e.output))
                    except Exception as e:
                        print(repr(e))
            except zipfile.error as e:
                logfile.write('%s is not a zip file. (url=%s): %s\n' % (fileobj, u, e))

    #Log error message if number of files downloaded does not match the number of links found
    if len(links)!=counter:
        print ("ERROR: %s Download(s) missing" % (len(links)-counter))
        logfile.write("ERROR: %s Download(s) missing\n" % (len(links)-counter))
    print("%s links found \t%s links downloaded" %(len(links), counter))
    logfile.write("%s links found \t%s links downloaded\n" %(len(links), counter))


    subprocess_results= ""
    try:
        subprocess_results = subprocess.check_output([r"C:\progra~1\PKWARE\PKZIPC\pkzipc.exe","-add", "-store", "-move", PATH +".zip", os.path.join(PATH, "*.zip")],  stderr=subprocess.STDOUT)
        logfile.write(repr(subprocess_results)+"\n")
    except CalledProcessError as e:
        print(repr(e.returncode))
        print(repr(e.cmd))
        print(repr(e.output))
    except Exception as e:
        print(repr(e))
    logfile.close()



    #run program above asking for inputs for fiscal year(s) and save directory
def main(user_path):
    #check input for alphanumeric year from 2003 to current year
    while True:
        y = input("Enter Fiscal Year or Year Range: ")
        #if user input contains '-' download year range otherwise
        if "-" in y: ylist = y.split("-")
        else: ylist = [y]
        #Change year(s) to integer
        try:
            ylist = [int(n) for n in ylist]
        except:
            print ('Year(s) out of bounds')
            continue
        #only accept one year or two years divided by a '-'
        if len(ylist)>2:
            print ('Year(s) out of bounds')
            continue
        #If year is a 1 or 2 digit number add 2000
        count = 0
        ylist[:] = [YEAR + 2000 if 0 < YEAR < 99 else YEAR for YEAR in ylist]
        #Check that 2nd year is greater than first year
        if len(ylist)==2 and ylist[0] > ylist[1]:
            print ('Year(s) out of bounds')
            continue
        #Check that year is between 2003 and current year
        for YEAR in ylist:
            if 2003 < YEAR <= datetime.now().year:
                count += 1
            else:
                print ('Year(s) out of bounds')
        if count==len(ylist):
            break
    #Convert year range to list of years
    if len(ylist) == 2:
        ylist = list(range(ylist[0],ylist[1]+1))
    t = input("Enter Download Delay (in hours): ")
    time.sleep(int(t)*3600) #time.sleep uses seconds
    for YEAR in ylist:
        #Create folder(s) in path named FPDS_FY + 'user year'
        os.makedirs(os.path.normpath(os.path.join(user_path, "FPDS_FY"+str(YEAR))),exist_ok=True)
        PATH = os.path.normpath(os.path.join(user_path, "FPDS_FY"+str(YEAR)))
        fpds_dl(YEAR, PATH)


# run the whole above program while using the tracer object to log which lines got executed.  This is separate from "logging," the file I/O log above
tracer.run('main(user_path)')
#now write the trace results to disk
r = tracer.results()
r.write_results(show_missing=True, coverdir=user_path)
print ("\a") #beap when done