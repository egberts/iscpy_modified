#!/usr/bin/env python

# Copyright (c) 2009, Purdue University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright notice, this
# list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
#
# Neither the name of the Purdue University nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import copy
import cPickle
import json

def ParseTokens(char_list):
  """Parses exploded isc named.conf portions.

  Inputs:
    char_list: List of isc file parts

  Outputs:
    dict: fragment or full isc file dict
    Recursive dictionary of isc file, dict values can be of 3 types,
    dict, string and bool. Boolean values are always true. Booleans are false
    if key is absent. Booleans represent situations in isc files such as:
      acl "registered" { 10.1.0/32; 10.1.1:/32;}}

    Example:

    {'stanza1 "new"': 'test_info', 'stanza1 "embedded"': {'acl "registered"':
        {'10.1.0/32': True, '10.1.1/32': True}}}
  """
  index = 0
  dictionary_fragment = {}
  new_char_list = copy.deepcopy(char_list)
  if( type(new_char_list) == str ):
    return new_char_list
  if( type(new_char_list) == dict ):
    return new_char_list
  last_open = None
  continuous_line = False
  temp_list = []

  while( index < len(new_char_list) ):
    if( new_char_list[index] == '{' ):
      last_open = index
    if( new_char_list[index] == ';' and continuous_line ):
      dictionary_fragment = temp_list
      temp_list = []
      continuous_line = False
    if( new_char_list[index] == ';' ):
      continuous_line = False
    if( len(new_char_list) > index + 1 and
        new_char_list[index] == '}'    and
        new_char_list[index + 1] != ';' ):
      skip, value = Clip(new_char_list[last_open:])
      temp_list.append({key: copy.deepcopy(ParseTokens(value))})
      continuous_line = True
    if( len(new_char_list) > index + 1 and new_char_list[index + 1] == '{' ):
      key = new_char_list.pop(index)
      skip, dict_value = Clip(new_char_list[index:])
      if( continuous_line ):
        temp_list.append({key: copy.deepcopy(ParseTokens(dict_value))})
      else:
        dictionary_fragment[key] = copy.deepcopy(ParseTokens(dict_value))
      index += skip
    else:
      if( len(new_char_list[index].split()) == 1 and '{' not in new_char_list ):
        for item in new_char_list:
          if( item in [';'] ):
            continue
          dictionary_fragment[item] = True

      #If there are more than 1 'keywords' at new_char_list[index]
      #ex - "recursion no;"
      elif( len(new_char_list[index].split()) >= 2 ):
        dictionary_fragment[new_char_list[index].split()[0]] = ' '.join(new_char_list[
            index].split()[1:])
        index += 1

      #If there is just 1 'keyword' at new_char_list[index]
      #ex "recursion;" (not a valid option, but for example's sake it's fine)
      elif( new_char_list[index] not in ['{', ';', '}'] ):
        key = new_char_list[index]
        dictionary_fragment[key] = ''
        index += 1
      index += 1

  return dictionary_fragment

def Clip(char_list):
  """Clips char_list to individual stanza.

  Inputs:
    char_list: partial of char_list from ParseTokens

  Outputs:
    tuple: (int: skip to char list index, list: shortened char_list)
  """
  assert(char_list[0] == '{')
  char_list.pop(0)
  skip = 0
  for index, item in enumerate(char_list):
    if( item == '{' ):
      skip += 1
    elif( item == '}' and skip == 0 ):
      return (index, char_list[:index])
    elif( item == '}' ):
      skip -= 1
  raise Exception("Invalid brackets.")

def Explode(isc_string):
  """Explodes isc file into relevant tokens.

  Inputs:
    isc_string: String of isc file

  Outputs:
    list: list of isc file tokens delimited by brackets and semicolons
      ['stanza1 "new"', '{', 'test_info', ';', '}']
  """
  str_array = []
  temp_string = []
  prev_char = ''
  for char in isc_string:
    if( char in ['\n'] ):
      continue
    if( char in ['{', '}', ';'] ):
      if( ''.join(temp_string).strip() == '' ):
        str_array.append(char)
      else:
        str_array.append(''.join(temp_string).strip())
        str_array.append(char)
        temp_string = []
    else:
      temp_string.append(char)
    prev_char = char
  return str_array

def SplitKeys(str_array):
    """Split key include to nested element
    Initial:
        somekey somekeyvalue1;
        somekey somekeyvalue2;
        ...
    Output:
        somekey {
            val1 somekeyvalue1;
            val2 somekeyvalue2;
        };
    """
    new_str_array = copy.deepcopy(str_array)
    tokens = []
    brackets = []
    num_val = 1
    # If next element is not ';', skip
    for idx, element in enumerate(new_str_array):
        if (element == '{'):
            brackets.append(element)
        elif (element == '}'):
            a = brackets.pop()
        elif (  len(element.split()) >= 2 and new_str_array[idx + 1] == ';' and len(brackets) == 0):
            str_path = 'val' + str(num_val) + ' ' + element.split()[1]
            if ( ( element.split()[0] not in tokens ) ):
                tokens.append(element.split()[0])
                new_str_array[idx] = element.split()[0]
                new_str_array.insert(idx + 1, '{')
                new_str_array.insert(idx + 2, str_path)
                new_str_array.insert(idx + 3, ';')
                new_str_array.insert(idx + 4, '}')
            else:
                del new_str_array[idx + 1]
                del new_str_array[idx]
                idx_token = new_str_array.index(element.split()[0])
                new_str_array.insert(idx_token + 2, str_path)
                new_str_array.insert(idx_token + 3, ';')
            num_val += 1
    return tokens, new_str_array


def ScrubComments(isc_string):
  """Clears comments from an isc file

  Inputs:
    isc_string: string of isc file
  Outputs:
    string: string of scrubbed isc file
  """
  isc_list = []
  if( isc_string is None ):
    return ''
  expanded_comment = False
  for line in isc_string.split('\n'):
    no_comment_line = ""
    # Vet out any inline comments
    if( '/*' in line.strip() ):
      try:
        striped_line = line.strip()
        chars = enumerate(striped_line)
        while True:
          i, c = chars.next()
          try:
            if c == '/' and striped_line[i+1] == '*':
              expanded_comment = True
              chars.next()  # Skipp '*'
              continue
            elif c == '*' and striped_line[i+1] == '/':
              expanded_comment = False
              chars.next()  # Skipp '/'
              continue
          except IndexError:
            continue  # We are at the end of the line
          if expanded_comment:
            continue
          else:
            no_comment_line += c
      except StopIteration:
        if no_comment_line:
          isc_list.append(no_comment_line)
        continue

    if( expanded_comment ):
      if( '*/' in line.strip() ):
        expanded_comment = False
        isc_list.append(line.split('*/')[-1])
        continue
      else:
        continue
    if( line.strip().startswith(('#', '//')) ):
      continue
    else:
      isc_list.append(line.split('#')[0].split('//')[0].strip())
  return '\n'.join(isc_list)

def MakeISC(isc_dict, terminate=True):
  """Outputs an isc formatted file string from a dict

  Inputs:
    isc_dict: a recursive dictionary to be turned into an isc file
              (from ParseTokens)

  Outputs:
    str: string of isc file without indentation
  """
  if( terminate ):
    terminator = ';'
  else:
    terminator = ''
  if( type(isc_dict) == str ):
    return isc_dict
  isc_list = []
  for option in isc_dict:
    if( type(isc_dict[option]) == bool ):
      isc_list.append('%s%s' % (option, terminator))
    elif( type(isc_dict[option]) == str or
        type(isc_dict[option]) == unicode):
      isc_list.append('%s %s%s' % (option, isc_dict[option], terminator))
    elif( type(isc_dict[option]) == list ):
      new_list = []
      for item in isc_dict[option]:
        new_list.append(MakeISC(item, terminate=False))
      new_list[-1] = '%s%s' % (new_list[-1], terminator)
      isc_list.append('%s { %s }%s' % (option, ' '.join(new_list), terminator))
    elif( type(isc_dict[option]) == dict ):
      isc_list.append('%s { %s }%s' % (option, MakeISC(isc_dict[option]), terminator))
  return '\n'.join(isc_list)

def ParseISCString(isc_string):
  """Makes a dictionary from an ISC file string

  Inputs:
    isc_string: string of isc file

  Outputs:
    dict: dictionary of ISC file representation
  """
  isc_specialkeys, isc_array = SplitKeys(Explode(ScrubComments(isc_string)))
  isc_dict = ParseTokens(isc_array)
  return isc_dict, isc_specialkeys

def Serialize(isc_string):
  """Makes a pickled string of a dict from an ISC file string

  Inputs:
    isc_string: string of an isc file

  Outputs:
    serialized_isc: serialized string of isc dict
  """
  return u'%s' % cPickle.dumps(ParseISCString(isc_string))

def Deserialize(serialized_string):
  """Makes an iscpy dict from a serliazed ISC dict

  Inputs:
    isc_string: string of an isc file

  Outputs:
    deserialized_isc: unserialized dict of serialized isc dict
  """
  return u'%s' % MakeISC(cPickle.loads(str(serialized_string)))

def AddZone(json_zone, isc_dict):
    """Add zone to named config

    Inputs:
        json_zone: Zone definition in json format

    Outputs:
        isc dict with added value
    """
    isc_dict.update(json_zone)
    return isc_dict

def ContentToWrite(isc_dict, num_tab, content, tokens):
    """
        Print ISC dictionary to specific file
    """
    s = ''
    for key, val in isc_dict.items():
        if key in tokens:
            for childkey, childval in val.items():
                s = key + ' ' + str(childval) + ';\n'
                content.append(s)
                s = ''
            content.append('\n')
        elif (isinstance(val, dict)):
            for tab in range (0, num_tab):
                s += "\t"
            s += key + " {\n"
            content.append(s)
            num_tab += 1
            ContentToWrite(val, num_tab, content, tokens)
            if num_tab >= 1:
                num_tab -= 1
            s = ''
            for tab in range (0, num_tab):
                s += "\t"
            s += "};\n"
            content.append(s)
            if num_tab == 0:
                content.append("\n")
            s = ''
        else:
            for tab in range (0, num_tab):
                s += "\t"
            s += key + " " + str(val) + ";\n"
            content.append(s)
            s = ''
    if num_tab == 0:
        return content

def WriteToFile(isc_dict, isc_specialkeys, filename):
    with open(filename, "w") as f:
        conts = ContentToWrite(isc_dict, 0, [], isc_specialkeys)
        for c in conts:
            f.write(c)
