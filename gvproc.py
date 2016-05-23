#!/usr/bin/env python
#Author: Richard Barnes (rbarnes@umn.edu)
import os
import gvParserLib
import sys
import sqlite3
import csv
import collections
import argparse

def NewDatabase(cur):
  cur.execute('''CREATE TABLE texts (time DATETIME, number TEXT, message TEXT, texttype TEXT)''')
  cur.execute('''CREATE TABLE audio (time DATETIME, number TEXT, duration INTEGER, type TEXT, text TEXT, confidence REAL, filename TEXT)''')
  cur.execute('''CREATE TABLE calls (time DATETIME, number TEXT, duration INTEGER, calltype TEXT)''')
  cur.execute('''CREATE TABLE contacts (name TEXT, number TEXT UNIQUE, notes TEXT)''')

def ReadGVoiceRecords(directory,mynumbers):
  records         = []
  files_processed = 0
  for fl in os.listdir(directory):
    if fl.endswith(".html"):
      record = gvParserLib.Parser.process_file(os.path.join(directory, fl),mynumbers)

      files_processed+=1
      if files_processed%100==0:
        print "Processed %d files." % (files_processed)

      if record:
        records.append(record)

  return records

def ReadContactsFile(filename):
  '''Return a dictionary of names and the numbers associated with them'''
  fin      = csv.DictReader(open(filename,'r'))
  contacts = [x for x in fin]
  cdict    = {}
  notedict = {}

  #Ensure that each number is unique
  non_unique = collections.Counter(x['Number'] for x in contacts)
  non_unique = [x for x in non_unique if non_unique[x]>1]
  if len(non_unique)>0:
    print "There were non-unique numbers in the contacts CSV!"
    sys.exit(-1)

  for c in contacts:
    if not c['Name'] in cdict:
      cdict[c['Name']] = []
    cdict[c['Name']].append(c['Number'])
    notedict[c['Number']] = c['Notes']

  return [cdict,notedict]

def FixContactNumbers(records,csvcontacts,mynumbers):
  '''Go through each record and use it to build a database of names and numbers.
     Use this database to fill in missing information for contacts.'''
  contacts = [x.contact for x in records]

  names_to_numbers = {}
  numbers_to_names = {}

  #Get frequency counts of numbers to resolve ambiguities
  number_freq = collections.Counter(x.contact.phonenumber for x in records)
  name_freq   = collections.Counter(x.contact.name for x in records)

  #Construct tables of names and numbers based on information found in the database
  for i in contacts:
    #Incomplete data. Can't use this.
    if not (i.phonenumber and i.name):
      continue

    if i.name in names_to_numbers and i.phonenumber!=names_to_numbers[i.name]:
      print "Ambiguity %s has number '%s' and '%s'. " % (i.name,i.phonenumber,names_to_numbers[i.name]),
      if number_freq[i.phonenumber]>number_freq[names_to_numbers[i.name]]:
        print "Using %s." % (i.phonenumber)
        names_to_numbers[i.name] = i.phonenumber
      else:
        print "Using %s." % (names_to_numbers[i.name])
    else:
      names_to_numbers[i.name] = i.phonenumber


    if i.phonenumber in numbers_to_names and i.name!=numbers_to_names[i.phonenumber]:
      print "Ambiguity %s has names '%s' and '%s'. " % (i.phonenumber,i.name,numbers_to_names[i.phonenumber]),
      if name_freq[i.name]>name_freq[numbers_to_names[i.phonenumber]]:
        print "Using %s." % (i.name)
        numbers_to_names[i.phonenumber] = i.name
      else:
        print "Using %s." % (numbers_to_names[i.phonenumber])
    else:
      numbers_to_names[i.phonenumber] = i.name

  names_to_numbers['###ME###'] = mynumbers[0]

  #Where our contacts database has information not in the GV dataset, fill the
  #gaps
  if csvcontacts:
    for c in csvcontacts:
      #contacts is a dictionary of names and lists of numbers associated with
      #them. Let us use the number frequency of the GV dataset to extract the
      #most appropriate number to use if a name does not have a number
      #associated with it

      #Loop through all of the numbers and add associated names to database
      for n in csvcontacts[c]:
        numbers_to_names[n] = c

      #Loop through all names and add an associated number to the database
      csvcontacts[c].sort(key=lambda x: number_freq[x])
      csvcontacts[c] = csvcontacts[c][0]

      #Fill the gaps
      if not c in names_to_numbers:
        names_to_numbers[c] = csvcontacts[c]
      if not csvcontacts[c] in numbers_to_names:
        numbers_to_names[c] = csvcontacts[c]

  for i in records:
    if not i.contact.name and i.contact.phonenumber in numbers_to_names:
      i.contact.name = numbers_to_names[i.contact.phonenumber]
    elif not i.contact.phonenumber and i.contact.name in names_to_numbers:
      i.contact.phonenumber = names_to_numbers[i.contact.name]

    if isinstance(i,gvParserLib.TextRecord):
      if not i.receiver.name and i.receiver.phonenumber in numbers_to_names:
        i.receiver.name = numbers_to_names[i.receiver.phonenumber]
      elif not i.receiver.phonenumber and i.receiver.name in names_to_numbers:
        i.receiver.phonenumber = names_to_numbers[i.receiver.name]

  return [records,numbers_to_names]

def WriteRecordsToSQL(cur,records):
  for i in records:
    if isinstance(i,gvParserLib.TextRecord):
      if i.contact.name=="###ME###":
        texttype = 'out'
        number   = i.receiver.phonenumber
        if not number:
          print "No number for %s" % (i.receiver.name)
      else:
        texttype = 'in'
        number   = i.contact.phonenumber
        if not number:
          print "No number for %s" % (i.contact.name)
      record = (str(i.date),number,i.text,texttype)
      cur.execute('INSERT INTO texts (time,number,message,texttype) VALUES (?,?,?,?)',record)
    elif isinstance(i,gvParserLib.AudioRecord):
      record = (str(i.date),i.contact.phonenumber,i.duration.total_seconds(),i.audiotype,i.text,i.confidence,i.filename)
      cur.execute('''INSERT INTO audio (time, number, duration, type, text, confidence, filename) VALUES (?,?,?,?,?,?,?)''',record)
    elif isinstance(i,gvParserLib.CallRecord):
      if i.calltype=="missed":
        duration = None
      else:
        duration = i.duration.total_seconds()
      record = (str(i.date),i.contact.phonenumber,duration,i.calltype)
      cur.execute('''INSERT INTO calls (time, number, duration, calltype) VALUES (?,?,?,?)''',record)

def WriteContactRecords(filename,numbers_to_names,number_notes):
  contact_records = [(numbers_to_names[x],x) for x in numbers_to_names]
  contact_records.sort()

  fout = csv.writer(open(filename,'w'))
  fout.writerow(['Name','Number'])
  for i in contact_records:
    note = number_notes.get(i[1],"")
    fout.writerow( (i[0],i[1],note) )

def ExplodeTextRecords(records):
  #Separate text conversations from non-text conversations
  texts     = filter(lambda x: isinstance(x,gvParserLib.TextConversationList),records)
  non_texts = filter(lambda x: not isinstance(x,gvParserLib.TextConversationList),records)

  #Explode text conversations into their constituent objects
  texts   = [i for x in texts for i in x]
  records = non_texts + texts

  return records

def ContactsToDB(cur,numbers_to_names,number_notes):
  numbers_to_names = [(numbers_to_names[x],x) for x in numbers_to_names]
  numbers_to_names = list(set(numbers_to_names))
  numbers_to_names.sort()
  for i in numbers_to_names:
    note = number_notes.get(i[1],"")
    #Ensure all records have notes, even if there are no notes
    try:
      cur.execute('''INSERT INTO contacts (name,number,notes) VALUES (?,?,?)''', (i[0],i[1],note) )
    except sqlite3.IntegrityError as e:
      print i
      print e
  print "Contacts loaded."


parser = argparse.ArgumentParser(description='Load Google Voice data into a database.')
parser.add_argument('--contacts', '-c', action='store', default=None, help='File to load contacts from.')
parser.add_argument('path',     help='Directory containing Google Voice files or Contacts file.')
parser.add_argument('database', help='Name of database to create or append to.')
parser.add_argument('--contactcsv','-f',action='store',default='contacts.csv',help="File to write discovered contacts to.")
parser.add_argument('--clear',  help='Clear database prior to inserting new Google Voice records.', action='store_const', const=True, default=False)
parser.add_argument('--mynumbers', '-m', action='store',default='',help="Comma-delimited list of this account's phone numbers")
args = parser.parse_args()

mynumbers = args.mynumbers.split(',')

if os.path.isfile(args.contactcsv):
  print "File '%s' already exists. Will not overwrite. Quitting" % (args.contactcsv)
  sys.exit(-1)

number_notes = {}
if args.contacts:
  [args.contacts, number_notes] = ReadContactsFile(args.contacts)

records = ReadGVoiceRecords(args.path,mynumbers)
if len(records)==0:
  print "Found no Google voice records!"
  sys.exit(-1)
else:
  print "Read %d records." % (len(records))

records = ExplodeTextRecords(records)

[records,numbers_to_names] = FixContactNumbers(records,args.contacts,mynumbers)

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

WriteContactRecords(args.contactcsv,numbers_to_names,number_notes)

ContactsToDB(cur,numbers_to_names,number_notes)

"""
else:
  if not os.path.isfile(args.database):
    print "Database does not exist!"
    sys.exit(-1)

  conn = sqlite3.connect(args.database)
  cur  = conn.cursor()

  cur.execute('DELETE FROM contacts;')
  ContactsToDB(cur,args.path)
  conn.commit()
"""

conn.commit()