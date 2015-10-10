##gvoiceParser

The gvoiceParser project aims to make the thousands of tiny files generated from
[Google Voice Takeout][1] more useful. This effort consists of three parts:

 1. A Python library for interpreting the HTML files ("gvParserLib.py")
 2. A program to invoke the library and load its contents into an SQLite
    database ("gvproc.py")

Note that this is currently a Python 2.7 script, with dependencies on `dateutil`
and `html5lib`.

Library Usage
=============
A GoogleVoice dump gives you a boatload of useless HTML files.

`gvoiceParser.Parser.process_file` in "gvParserLib.py" processes one such file.
If it is successful, it returns a record. Otherwise, it returns `None`.

You can use it in a loop, like so, to read all the GoogleVoice files

    for fl in os.listdir(directory):
      if fl.endswith(".html"):
        record = gvoiceParser.Parser.process_file(os.path.join(directory, fl),mynumbers)
        #Do other bookkeeping stuff here
        if record:
          records.append(record)

What's that `mynumbers` business, you ask? That is a list of all the numbers the
Google Voice account holder owns. Typically, this is the Google Voice number
itself along with any phones the GV number aliases, such as the user's real cell
number. This list allows the parser to associate these numbers with the caller
named "###ME###", which is otherwise difficult.

The records contain fields which are pretty self-explanatory. If you're
ambitious, you can even send me a patch with a description of them, which I will
place here.

Usage for the Rest of Us
========================

What's that? You want your GV numbers in a nice database so you can back-up them
up or do stats or something? Got you covered.

There's a handy file in the repo named "gvproc.py".

The command takes the following arguments

 * `--contacts` This is a file to load contacts from.
   The file should be a CSV with the header row `Name,Number,Notes`.
   Each number must be unique, but any number of names can be identical.
   When a person gets a new phone number this allows you to continue to
   associate that person's name with each of their numbers in your DB.

 * `path` Where the GV files are

 * `database` Name of the database you want to create or append to.
   **Note that currently appending will create duplicate messages.**

 * `--contactcsv` The program uses some moderately intelligent logic to try to
   figure out which phone numbers belong to which names. The aforementioned
   contacts CSV ensures that contacts you already know are associated with the
   correct name. This argument specifies a CSV where all contacts, new and old,
   are printed to. You can then diff this against the original contacts CSV and
   revise it accordingly. I recommend then re-running the program so that your
   DB comes out right.

 * `--clear` This destroys all messages, texts, and call records, but not
   contacts, in the DB.

 * `--mynumbers` This is a comma-delimited list of the account owner's phone
   numbers. This is useful because you do not often have yourself in your
   contacts list.

Notes
=====

If you need to parse Google Voice messages stored in Hangouts, Steven Zhang has
a repo [here][3] which may help.

Credits
=======
The "gvoiceParser.py" library was original built by [Avi
Levin](https://github.com/Arithmomaniac) and released under the LGPL v2.1. They
have since modified their repository to identify [Richard's
repo](https://github.com/r-barnes/gvoiceParser) as the primary development
effort.

Avi's work, "gvoiceParser.py" library was, in turn, a rewrite of their
[googlevoice-to-sqlite][2] script.

  [1]: https://www.google.com/settings/takeout
  [2]: https://code.google.com/p/googlevoice-to-sqlite/
  [3]: https://github.com/stevenqzhang/hangout-slack-import