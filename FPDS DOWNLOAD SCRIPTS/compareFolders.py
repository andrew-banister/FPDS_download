# compareFolders
###############################
# Programmer: Andrew Banister
# Date: September 2016
# Purpose: Compares two folders matching by name.
#          Compares file size, file date, and file hash


import os
import csv
import datetime
import hashlib
import ctypes

def filemd5(fname):
    """Return MD5 hash of a file
    """
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def getStats(path, md5_on):
    """Get file stats

    Return file name, file size, file modified time, and md5 hash
    """
    for pathname, dirnames, filenames in os.walk(path):
        for filename in ( os.path.join(pathname, x) for x in filenames ):
            stat = os.stat(filename)
            if md5_on: statmd5 = filemd5(filename)
            else: statmd5 = None
            yield filename[len(path):], stat.st_size, stat.st_mtime, statmd5

def compareFolders(path1,path2,output):
    """Compare two folders

    Take two folders and compare the file contents. Output a csv file.
    """
    md5_on = ctypes.windll.user32.MessageBoxW(0, "Do you want to run md5 hash "
        "check?\nNote: The script could take several hours instead of less than"
        " a minute.", "md5 Confirmation", 4)==6
    FileFolder1=list(getStats(path1, md5_on))
    FileFolder2=list(getStats(path2, md5_on))
    dict1 = dict((each[0], each[1:]) for each in FileFolder1)
    dict2 = dict((each[0], each[1:]) for each in FileFolder2)
    dictall = dict((k, [dict1[k], dict2.get(k)]) for k in dict1)
    dictall.update((k, [(None,None,None), dict2[k]]) 
        for k in dict2 if k not in dict1)
    dictall.update((k, [dict1[k],(None,None,None)]) 
        for k in dict1 if k not in dict2)
    
    with open (os.path.join(output, "compareFolders.csv"),'w') as csvfile:
        fields = ('File Name', 'File Size 1', 'File Size 2', 
            'File Size % Difference', 'File Date 1', 'File Date 2', 
            'File Date Same?') + md5_on 
            * ('File Hash 1', 'File Hash 2', 'File Hash Same?')
        csv_compare = csv.DictWriter(
            csvfile, fieldnames=fields, lineterminator = '\n')
        csv_compare.writerow({'File Name': "File 1: %s" % path1})
        csv_compare.writerow({'File Name': "File 2: %s" % path2})
        csv_compare.writerow({'File Name': ""})

        csv_compare.writeheader()
        for key, value in sorted(dictall.items()):
            print("Checking %s." %(key))                 
            filename = key
            filesize1 = value[0][0]
            filesize2 = value[1][0]
            if None not in {filesize1,filesize2}:
                percdif = (filesize2-filesize1)/filesize1*100
            else: percdif=None
            if value[0][1]!=None:
                date1 = datetime.datetime.fromtimestamp(
                    value[0][1]).strftime('%Y-%m-%d %H:%M:%S')
            else: date1=None
            if value[1][1]!=None:
                date2 = datetime.datetime.fromtimestamp(
                    value[1][1]).strftime('%Y-%m-%d %H:%M:%S')
            else: date2=None
            datesame = value[0][1] == value[1][1]
            hash1 = value[0][2]
            hash2 = value[1][2]
            hashsame = hash1 == hash2
            row = {'File Name':filename, 'File Size 1':filesize1, 
                'File Size 2':filesize2, 'File Size % Difference':percdif, 
                'File Date 1':date1,'File Date 2':date2, 
                'File Date Same?':datesame}
            if md5_on: row.update({'File Hash 1': hash1, 'File Hash 2': hash2, 
                'File Hash Same?':hashsame})
            csv_compare.writerow(row)
    return(dictall)

#path for folders to compare
p1=r""
p2=r""
#output path
PATH=r""
compareFolders(p1,p2,PATH)