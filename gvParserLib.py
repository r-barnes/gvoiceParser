import datetime
import re
import htmlentitydefs
from dateutil import tz
import dateutil.parser
import html5lib

#Contacts
class Contact(object):
    __slots__ = ['name', 'phonenumber']
    def __init__(self, phonenumber = None, name = None):
        self.phonenumber = phonenumber
        self.name = name
    def __repr__(self):
        return "Contact(%s, %s)" % (repr(self.name), repr(self.phonenumber))
    def dump(self):
        ''' Returns a string that encodes the information inside the object.'''
        return "%s (%s)" % (self.name, self.phonenumber)
    def __str__(self):
        return "Contact: %s" % self.dump()
    def __nonzero__(self):
        ''' Returns whether or not the object has no effective information'''
        return bool(self.phonenumber) or bool(self.name)
    def __eq__(self,other):
        return self.phonenumber==other.phonenumber
    def __hash__(self):
        return hash(self.phonenumber)

    @staticmethod
    def get_node(node):
        '''Given an HTML node, finds the self-or-descendant that encodes a Contact'''
        if node.tag == "{http://www.w3.org/1999/xhtml}a" and node.attrib["class"] == "tel":
            return node
        contactnode = node.find(Parser.as_xhtml('.//cite[@class="sender vcard"]/a[@class="tel"]'))
        if not contactnode:
            contactnode = node.find(Parser.as_xhtml('.//div[@class="contributor vcard"]/a[@class="tel"]'))
        return contactnode

    @classmethod
    def from_node(cls, node):
        ''' finds and returns the first contact found beneath the node in the tree'''
        #get the right node
        contactnode = cls.get_node(node);
        contact_obj = cls()
        #name
        contact_obj.name = contactnode.findtext(Parser.as_xhtml('./span[@class="fn"]'))
        if not contact_obj.name: #If a blank string or none.
            contact_obj.name = None
        #phone number
        contactphonenumber = re.search('\d+', contactnode.attrib['href'])
        if contactphonenumber:
            contact_obj.phonenumber = contactphonenumber.group(0)

        return contact_obj

class GVoiceRecord(object):
    """The base class of a GVoice-parsed object"""
    __slots__ = ['contact', 'date']
    def __init__(self, contact = None, date = None):
        super(GVoiceRecord, self).__init__()
        self.contact = Contact() if contact is None else contact
        self.date = date
    def __repr__(self):
        return "GVoiceRecord(%s, %s)" % (repr(self.contact), repr(self.date))
    def dump(self):
        ''' Returns a string that encodes the information inside the object.'''
        return "%s; %s" % (self.contact.dump(), self.date)
    #All GVoiceRecord objects output as strings their types and dump data
    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self.dump())
    def __nonzero__(self):
        ''' Returns whether or not the object has no effective information'''
        return bool(self.date)

    @classmethod
    def from_node(cls, node, date_class):
        ''' finds and returns the first GVoiceRecord beneath the node in the tree.'''
        record_obj = cls()
        record_obj.contact = Contact.from_node(node)
        record_obj.date = ParseTools.parse_date(node.find(Parser.as_xhtml('./abbr[@class="%s"]' % date_class)).attrib["title"])
        return record_obj

class TelephonyRecord(GVoiceRecord):
    __slots__ = ['duration']
    def __init__(self, contact = None, date = None, duration = None):
        super(TelephonyRecord, self).__init__(contact, date);
        self.duration = duration
    def __repr__(self):
        return "TelephonyRecord(%s, %s, %s)" % (repr(self.contact), repr(self.date), repr(self.duration))
    def dump(self):
        ''' Returns a string that encodes the information inside the object.'''
        return_text = super(TelephonyRecord, self).dump();
        if self.duration is not None:
            return_text += '(%s)' % self.duration
        return return_text
    def __nonzero__(self):
        ''' Returns whether or not the object has no effective information'''
        return super(TelephonyRecord, self) and bool(self.contact)

    @staticmethod
    def get_node(node):
        '''Given an HTML node, finds the self-or-descendant that encodes a TelephonyRecord'''
        if node.tag == "{http://www.w3.org/1999/xhtml}div" and node.attrib["class"] == "haudio":
            return node

        node = node.find(Parser.as_xhtml('.//div[@class="haudio"]'))
        return node if node else None

    @classmethod
    def from_node(cls, node):
        ''' finds and returns the first TelephonyRecord beneath the node in the tree.'''
        # !!! FIX: Should we do this somewhere else?
        #zoom in, make sure is the right type
        node = cls.get_node(node)
        if node is None:
            return None
        base_obj = GVoiceRecord.from_node(node, "published")
        telephony_obj = cls(base_obj.contact, base_obj.date)

        duration_text = node.findtext(Parser.as_xhtml('./abbr[@class="duration"]'))
        if duration_text is not None: #but 0 is OK
            telephony_obj.duration = ParseTools.parse_time(duration_text)

        return telephony_obj


class CallRecord(TelephonyRecord):
    __slots__ = ['calltype']
    #callTypes = ['Placed', 'Received', 'Missed']
    def __init__(self, contact = None, date = None, duration = None, calltype = None):
        super(CallRecord, self).__init__(contact, date, duration)
        self.calltype = calltype
    def __repr__(self):
        return "CallRecord(%s, %s, %s, %s)" % (repr(self.contact), repr(self.date), repr(self.duration), repr(self.calltype))
    def dump(self):
        ''' Returns a string that encodes the information inside the object.'''
        return '%s; %s' % (self.calltype, super(CallRecord, self).dump())
    def __nonzero__(self):
        ''' Returns whether or not the object has no effective information'''
        return super(CallRecord, self) and bool(self.calltype)

    @staticmethod
    def get_node(node):
        '''Given an HTML node, finds the self-or-descendant that encodes a CallRecord'''
        node = TelephonyRecord.get_node(node)
        if node is None:
            return None
        if node.find(Parser.as_xhtml('./audio')): #is audio, not call
            return None
        return node

    @classmethod
    def from_node(cls, node):
        ''' finds and returns the first CallRecord found beneath the node in the tree'''

        node = cls.get_node(node)

        if node is None:
            return None

        base_obj = TelephonyRecord.from_node(node)
        calltype = ParseTools.get_label(node)

        return cls(base_obj.contact, base_obj.date, base_obj.duration, calltype)

class AudioRecord(TelephonyRecord):
    __slots__ = ['audiotype', 'text', 'confidence', 'filename']
    #audioTypes = ['Recording', 'Voicemail']
    def __init__(self, contact = None, date = None, duration = None,
                 audiotype = None, text = None, confidence = None, filename = None):
        super(AudioRecord, self).__init__(contact, date, duration)
        self.audiotype = audiotype
        self.text = text
        self.confidence = confidence
        self.filename = filename
    def __repr__(self):
        return "AudioRecord(%s, %s, %s, %s, %s, %s, %s)" % (repr(self.contact), repr(self.date), repr(self.duration),
                                                            repr(self.audiotype), repr(self.text), repr(self.confidence), repr(self.filename))
    def dump(self):
        ''' Returns a string that encodes the information inside the object.'''
        return_text = '%s; %s' % (self.audiotype, super(AudioRecord, self).dump())
        if self.text:
            if self.confidence:
                return_text += ' [%0.2f]' % self.confidence
            return_text += self.text
        return return_text
    def __nonzero__(self):
        ''' Returns whether or not the object has no effective information'''
        return super(AudioRecord, self) and bool(self.audiotype)

    @staticmethod
    def get_node(node):
        '''Given an HTML node, finds the self-or-descendant that encodes an AudioRecord'''
        node = TelephonyRecord.get_node(node)
        if node is None:
            return None
        if not node.find(Parser.as_xhtml('./audio')): #is audio, not call
            return None
        return node

    @classmethod
    #Processes voicemails, recordings
    def from_node(cls, node):
        ''' finds and returns the first AudioRecord beneath the node in the tree.'''
        node = cls.get_node(node)

        if node is None:
            return None

        base_obj = TelephonyRecord.from_node(node)
        audio_obj = cls(base_obj.contact, base_obj.date, base_obj.duration)

        descriptionNode = node.find(Parser.as_xhtml('./span[@class="description"]'))
        if descriptionNode and descriptionNode.findtext(Parser.as_xhtml('./span[@class="full-text"]')):
            #!!! FIX: html decode
            fullText = descriptionNode.findtext(Parser.as_xhtml('./span[@class="full-text"]'))
            if fullText != 'Unable to transcribe this message.':
                audio_obj.text = fullText

            confidence_values = descriptionNode.findall(Parser.as_xhtml('./span/span[@class="confidence"]'))
            totalconfid = sum( float(i.findtext('.')) for i in confidence_values )
            audio_obj.confidence = totalconfid / len(confidence_values)
        audio_obj.filename = node.find(Parser.as_xhtml('./audio')).attrib["src"]
        audio_obj.audiotype = ParseTools.get_label(node)
        return audio_obj

class TextRecord(GVoiceRecord):
    __slots__ = ['text','receiver']
    def __init__(self, contact = None, date = None, text = None):
        super(TextRecord, self).__init__(contact, date)
        self.text     = text
        self.receiver = Contact()
    def __repr__(self):
        return "TextRecord(%s, %s, %s)" % (self.contact, self.date, self.text)
    def dump(self):
        ''' Returns a string that encodes the information inside the object.'''
        return '%s %s' % (super(TextRecord, self).dump(), self.text)
    def __nonzero__(self):
        ''' Returns whether or not the object has no effective information'''
        return super(TextRecord, self) and bool(self.text) is not None

    @classmethod
    def from_node(cls, node):
        ''' finds and returns the first TextRecord beneath the node in the tree.'''
        base_obj = GVoiceRecord.from_node(node, "dt")
        # !!! FIX: html decode the text content
        text = ParseTools.unescape(node.findtext(Parser.as_xhtml('./q')))

        return cls(base_obj.contact, base_obj.date, text)

class TextConversationList(list):
    __slots__ = ['contact']
    def __init__(self):
        super(TextConversationList, self).__init__()
        self.contact = Contact()
    def dump(self):
        ''' Returns a string that encodes the information inside the object.'''
        return '%s %s' % (self.contact.dump(), list(txt.dump() for txt in self))

    @staticmethod
    def get_node(node):
        '''Given an HTML node, finds the self-or-descendant that encodes a TextConversationList'''
        if node.tag == "{http://www.w3.org/1999/xhtml}div" and node.attrib["class"] == "hChatLog hfeed":
            return node
        conversationnode = node.find(Parser.as_xhtml('.//div[@class="hChatLog hfeed"]'))
        return conversationnode if conversationnode else None

    @classmethod
    def from_node(cls, node, onewayname, filename, mynumbers):
        ''' finds and returns the first TextConversationList beneath the node in the tree.
        The onewayname parameter is used to set the contact for outgoing texts when there is no replay'''
        '''*mynumbers* is a list of the phone numbers the account user uses'''
        #get node of interest
        conversationnode = cls.get_node(node)
        if conversationnode is None:
            return None

        #now move on to main exec
        textnodes = conversationnode.findall(Parser.as_xhtml('./div[@class="message"]'))
        #!!! FIX? Why is this necessary?
        if not textnodes:
            return None

        #Read each text message, making a note of whether I sent it
        txtConversation_obj = cls()
        conv_with           = None
        for txtNode in textnodes:
            txtmsg = TextRecord.from_node(txtNode)

            #TODO: Skip Google Voice error messages
            if txtmsg.contact.name=='Google Voice':
                continue
            if not txtmsg.contact.name and not txtmsg.contact.phonenumber:
                continue

            if txtmsg.contact.phonenumber in mynumbers:
                txtmsg.contact = Contact(name="###ME###",phonenumber=mynumbers[0])
            else:
                conv_with = txtmsg.contact
            txtConversation_obj.append(txtmsg)

        #All contacts on conversation
        unique_contacts = list(set(txt.contact for txt in txtConversation_obj))

        #I sent an unreplied out-going message
        if not conv_with:
            conv_with = Contact(None, onewayname)
            unique_contacts.append(conv_with)

        #I received a text and did not reply
        if len(unique_contacts)==1:
            unique_contacts.append(Contact(name="###ME###",phonenumber=mynumbers[0]))
        elif len(unique_contacts)>2:  #Multiway conversation
            print "Multiway conversation detected!"
            print filename
            print unique_contacts
            return txtConversation_obj

        #Note who I am conversing with. Clone by constructor
        txtConversation_obj.contact = Contact(name=conv_with.name,phonenumber=conv_with.phonenumber)

        #Set receivers for each text message in the conversation
        recipient = {unique_contacts[0]:unique_contacts[1], unique_contacts[1]:unique_contacts[0]}
        for i in txtConversation_obj:
            i.receiver = recipient[i.contact]

        return txtConversation_obj

#####--------------------------------

class ParseTools:
    @staticmethod
    #from effbot.org.
    def unescape(text):
        '''Unescapes the HTML entities in a block of text'''
        def fixup(m):
            text = m.group(0)
            if text[:2] == "&#":
                # character reference
                try:
                    if text[:3] == "&#x":
                        return unichr(int(text[3:-1], 16))
                    else:
                        return unichr(int(text[2:-1]))
                except ValueError:
                    pass
            else:
                # named entity
                try:
                    text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
                except KeyError:
                    pass
            return text # leave as is
        return re.sub("&#?\w+;", fixup, text)

    @staticmethod
    def parse_date (datestring):
        '''Parses a Gvoice-formatted date into a datetime object'''
        returntime = dateutil.parser.parse(datestring).astimezone(tz.tzutc())
        return returntime.replace(tzinfo = None)

    @staticmethod
    def parse_time (timestring):
        '''Parses a duration time-string/tag into a timedelta object'''
        timestringmatch = re.search('(\d\d+):(\d\d):(\d\d)', timestring)
        return datetime.timedelta (
            seconds = int(timestringmatch.group(3)),
            minutes = int(timestringmatch.group(2)),
            hours   = int(timestringmatch.group(1))
        )

    ##------------------------------------

    @staticmethod
    #!!! FEATURE: return Inbox, Starred flags
    def get_label(node):
        ''' Gets a category label for the HTML file '''
        labelNodes = node.findall(Parser.as_xhtml('./div[@class="tags"]/a[@rel="tag"]'))
        validtags = ('placed', 'received', 'missed', 'recorded', 'voicemail') #Valid categories
        for label in (node.attrib['href'].rsplit("#")[1] for node in labelNodes):
            if label in validtags: #last part of label href is valid label
                return label
        return None

##-------------------

class Parser:
    @staticmethod
    def as_xhtml(path):
        ''' turns a regular xpath expression into an XHTML one'''
        return re.sub('/(?=\w)', '/{http://www.w3.org/1999/xhtml}', path)

    @classmethod
    def process_file(cls, filename, mynumbers):
        '''gets the gvoiceParser object from a file location'''
        '''*mynumbers* is a list of the phone numbers the account user uses'''
        ##BEGIN DEBUG
        #tb = html5lib.getTreeBuilder("etree", implementation=etree.ElementTree)
        #p = html5lib.HTMLParser(tb)
        #with open(filename, 'r') as f: #read the file
        #    tree = p.parse(f, encoding="iso-8859-15")
        ##END DEBUG
        with open(filename, 'r') as f: #read the file
            tree = html5lib.parse(f, encoding="iso-8859-15")
        return cls.process_tree(tree, filename, mynumbers) #do the loading

    @staticmethod
    def process_tree(tree, filename, mynumbers):
        '''gets the gvoiceParser object from an element tree'''
        '''*mynumbers* is a list of the phone numbers the account user uses'''
        #TEXTS
        #print filename
        onewayname = tree.findtext(Parser.as_xhtml('.//title'));
        onewayname = onewayname[6::] if onewayname.startswith("Me to") else None
        #process the text files
        obj = TextConversationList.from_node(tree, onewayname, filename, mynumbers)
        if obj: #if text, then done
            return obj
        #CALLS
        obj = CallRecord.from_node(tree)
        if obj: #if text, then done
            return obj
        #AUDIO
        obj = AudioRecord.from_node(tree)
        if obj: #if text, then done
            return obj
        #should not get this far
        return None