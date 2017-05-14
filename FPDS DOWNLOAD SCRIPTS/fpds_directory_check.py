# FPDS Download
###############################
# Programmer: Andrew Banister
# Date: July - August 2016
# Purpose: Downloads all zip files from the Federal Procurement Data System for a particular fiscal year

#import string and download libraries
import zipfile, os, requests, sys, datetime, tkinter, re
from tkinter import filedialog
#import audit trail library
import trace


#set the directory to the path containing this script; doing so allows the tracing to work.
#otherwise you get errno 2; see: http://stackoverflow.com/questions/15725273/python-oserror-errno-2-no-such-file-or-directory
system_path = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(system_path)

# create a Trace object -- which will create a log file that counts the number of executions of each line below.
tracer = trace.Trace(
     #the goal of this line -- which comes straight from the sample code -- is to generate trace files only for GAO-written code and not more than a dozen trace files for Python-supplied code
     ignoredirs=[sys.prefix],
     #, sys.exec_prefix],
     trace=0,
     count=1)


def find_id(html_string):
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
    assert len(IDs) == len(foldergifs), 'All IDs not found. Check html directory. Found %s IDs and %s foldergifs' % (len(IDs), len(foldergifs))
    return IDs


def fpds_dl(year, PATH):
    """Downloads all FPDS data for a particular Fiscal Year.
    
    This builds URLs for each agency's zip file, then downloads and unzips the files.
    Log files are created containing an html of the directory, MORE
    
    Arg:
            year: The Fiscal Year you want to download.
    Returns:
            Nothing. Saves files.
    """
    #setup logfile
    print (PATH)
    logfile = open(PATH + "\\FPDS_check_directories_log_file.log",'w')
    logfile.write("fpds_dl.py run began at "+str(datetime.datetime.now())+"\n")

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
    elif 2015<= year <= datetime.datetime.now().year:
        suf = "-DEPT-1001" + str(year-1) + "TO0930" + str(year) + "-Archive.zip"
    else:
        logfile.write('%s Year out of bounds' % year)
        raise ValueError('%s Year out of bounds' % year)
    
    # Download directory_url
    f = requests.get(directory_url, stream = True)
    # Save directory
    with open(PATH + "\\FPDS_directory_FY" + str(year) + ".html", "w") as directory:
        directory.write(f.text)
        logfile.write("Directory of FPDS for FY " + str(year) + " saved at " +str(datetime.datetime.now())
        +" Filename: " + PATH + "\\FPDS_directory_FY" + str(year) + ".html\t"
        +str(os.stat(PATH + "\\FPDS_directory_FY" + str(year) + ".html").st_size) +" bytes.\n")
    #Get zipfile links of agency IDs 
    links = find_id(f.text)
    logfile.write("Agency IDs obtained: %r\n" % links)
    logfile.write("Zip urls found:\n")
    # Download files and unzip
    # create urls
    zip_urls=[]
    for l in links: #Change to links to dl all
        print (l)
        u = pref + l + "/" + l + suf #url contains the agency ID twice
        zip_urls.append(u)
        logfile.write(u+"\n")
    counter = 0
    for u in zip_urls: #uses i index for zip_urls and links
        try:
            request = requests.get(u, stream=True)
        except requests.exceptions.RequestException as e:
            logfile.write("Can't retrieve %s: %s" % (u, e))
            print("Can't retrieve %s: %s" % (u, e))
            return
        if "<title>Object not found!</title>" not in request.text:
            counter+= 1
    logfile.write("Links found: %s /t Links working: %s" %(len(links), counter))
    logfile.close()
        
    #run program above asking for inputs for fiscal year and save directory
def main():
    for YEAR in range(2004,2017):
        y = str(YEAR)[-2:]  
        #Setup tkinter to create filedirectory box
        root = tkinter.Tk()
        root.withdraw()
        x = filedialog.askdirectory()
        #Create folder in path named FPDS_FY + 'year typed in'
        os.makedirs(os.path.normpath(os.path.join(x, "FPDS_FY"+y)),exist_ok=True)
        PATH = os.path.normpath(os.path.join(x, "FPDS_FY"+y))
        fpds_dl(YEAR, PATH)


# run the whole above program while using the tracer object to log which lines got executed.  This is separate from "logging," the file I/O log above
tracer.run('main()')
#now write the trace results to disk
r = tracer.results()
r.write_results(show_missing=True, coverdir=system_path)