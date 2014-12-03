#!/usr/bin/env python
#Author: Richard Barnes (rbarnes@umn.edu)
import os
import gvoiceParser
import sys
import sqlite3
import csv
import collections
import argparse

def NewDatabase(cur):
  cur.execute('''CREATE TABLE texts (time DATETIME, sender TEXT, message TEXT)''')
  cur.execute('''CREATE TABLE audio (time DATETIME, caller TEXT, duration INTEGER, type TEXT, text TEXT, confidence REAL, filename TEXT)''')
  cur.execute('''CREATE TABLE calls (time DATETIME, caller TEXT, duration INTEGER, calltype TEXT)''')
  cur.execute('''CREATE TABLE contacts (name TEXT, number TEXT UNIQUE, notes TEXT)''')

def ReadGVoiceRecords(directory):
  records         = []
  files_processed = 0
  for fl in os.listdir(directory):
    if fl.endswith(".html"):
      record = gvoiceParser.Parser.process_file(os.path.join(directory, fl))

      files_processed+=1
      if files_processed%100==0:
        print "Processed %d files." % (files_processed)

      if record:
        records.append(record)

  return records

def WriteRecordsToSQL(cur,records):
  for i in records:
    if isinstance(i,gvoiceParser.TextConversationList):
      for r in i:
        if not isinstance(r,gvoiceParser.TextRecord):
          print "TextConversationList contains something that is not a TextRecord!"
          print i
          continue
        record = (str(r.date),r.contact.phonenumber,r.text)
        cur.execute('INSERT INTO texts (time,sender,message) VALUES (?,?,?)',record)
    elif isinstance(i,gvoiceParser.AudioRecord):
      record = (str(i.date),i.contact.phonenumber,i.duration.total_seconds(),i.audiotype,i.text,i.confidence,i.filename)
      cur.execute('''INSERT INTO audio (time, caller, duration, type, text, confidence, filename) VALUES (?,?,?,?,?,?,?)''',record)
    elif isinstance(i,gvoiceParser.CallRecord):
      if i.calltype=="missed":
        duration = "NULL"
      else:
        duration = i.duration.total_seconds()
      record = (str(i.date),i.contact.phonenumber,duration,i.calltype)
      cur.execute('''INSERT INTO calls (time, caller, duration, calltype) VALUES (?,?,?,?)''',record)

def WriteContactRecords(filename,records):
  contact_records = list(set(filter(lambda x: x[1] != None, map(lambda x: (x.contact.name,x.contact.phonenumber), records))))
  contact_records.sort()
  fout            = csv.writer(open(filename,'w'))
  fout.writerow(['Name','Number'])
  for i in contact_records:
    fout.writerow(i)

def ContactsToDB(cur,filename):
  fin = csv.reader(open(filename,'r'))
  fin.next()
  for i in fin:
    #Ensure all records have notes, even if there are no notes
    if len(i)==2:
      i.append(None)
    try:
      cur.execute('''INSERT INTO contacts (name,number,notes) VALUES (?,?,?)''',i)
    except sqlite3.IntegrityError as e:
      print i
      print e
  print "Contacts loaded."


parser = argparse.ArgumentParser(description='Load Google Voice data into a database.')
parser.add_argument('--contacts', '-c', action='store_const', const=True, default=False, help='Clear DB of existing contacts, insert new ones. Syntax: <DB> <CONTACTS FILE>')
parser.add_argument('path',     help='Directory containing Google Voice files or Contacts file.')
parser.add_argument('database', help='Name of database to create or append to.')
parser.add_argument('--contactcsv','-f',action='store',default='contacts.csv',help="File to write discovered contacts to.")
parser.add_argument('--clear',  help='Clear database prior to inserting new Google Voice records.', action='store_const', const=True, default=False)
args = parser.parse_args()

if not args.contacts:
  if os.path.isfile(args.contactcsv):
    print "File '%s' already exists. Will not overwrite. Quitting" % (args.contactcsv)
    sys.exit(-1)

  records = ReadGVoiceRecords(args.path)
  if len(records)==0:
    print "Found no Google voice records!"
    sys.exit(-1)
  else:
    print "Read %d records." % (len(records))


  db_existed = os.path.isfile(args.database)

  conn = sqlite3.connect(args.database)
  cur = conn.cursor()

  if not db_existed:
    NewDatabase(cur)

  if args.clear:
    cur.execute('DELETE FROM texts;')
    cur.execute('DELETE FROM audio;')
    cur.execute('DELETE FROM calls;')

  WriteRecordsToSQL(cur,records)

  WriteContactRecords(args.contactcsv,records)

else:
  if not os.path.isfile(args.database):
    print "Database does not exist!"
    sys.exit(-1)

  conn = sqlite3.connect(args.database)
  cur  = conn.cursor()

  cur.execute('DELETE FROM contacts;')
  ContactsToDB(cur,args.path)

conn.commit()