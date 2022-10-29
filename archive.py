#!/usr/bin/python
# -*- coding: latin-1 -*-

# Reggie Next - New Super Mario Bros. Wii Level Editor
# Milestone 4
# Copyright (C) 2009-2020 Treeki, Tempus, angelsl, JasonP27, Kamek64,
# MalStar1000, RoadrunnerWMC, AboodXD, John10v10, TheGrop, CLF78,
# Zementblock, Danster64

# This file is part of Reggie Next.

# Reggie Next is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Reggie Next is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Reggie Next.  If not, see <http://www.gnu.org/licenses/>.


# archive.py
# API for opening and saving Wii U8 archives.
# From the wii.py library.


################################################################
################################################################

import os
from common import Struct, WiiArchive, align


class U8(WiiArchive):
    """
    Class for a U8 (.arc) archive
    """

    class U8Header(Struct):
        """
        Class for the header of a U8 archive
        """
        __endian__ = Struct.BE

        def __format__(self):
            self.tag = Struct.string(4)
            self.rootnode_offset = Struct.uint32
            self.header_size = Struct.uint32
            self.data_offset = Struct.uint32
            self.zeroes = Struct.string(16)

    class U8Node(Struct):
        """
        Class for a single node of a U8 archive
        """
        __endian__ = Struct.BE

        def __format__(self):
            self.type = Struct.uint16
            self.name_offset = Struct.uint16
            self.data_offset = Struct.uint32
            self.size = Struct.uint32

    def __init__(self):
        """
        Initializes the U8
        """
        super().__init__()
        self.files = []

    def _dump(self):
        """
        Returns all data in this U8 archive as bytes
        """
        header = self.U8Header()
        rootnode = self.U8Node()

        # constants
        header.tag = b'U\xAA8-'
        header.rootnode_offset = 0x20
        header.zeroes = b'\x00' * 16
        rootnode.type = 0x0100

        nodes = []
        strings = b'\x00'
        data = b''

        for item, value in self.files:
            node = self.U8Node()

            recursion = item.count('/')
            if recursion < 0:
                recursion = 0
            name = item.split('/')[-1]

            node.name_offset = len(strings)
            strings += name.encode('latin-1') + b'\x00'

            if value is None:  # directory
                node.type = 0x0100
                node.data_offset = recursion

                node.size = len(nodes) + 1
                for one, two in self.files:
                    if one[:len(item)] == item:  # find nodes in the folder
                        node.size += 1
            else:  # file
                node.type = 0x0000
                node.data_offset = len(data)
                data += value + (b'\x00' * (
                    align(len(value), 32) - len(
                        value)))  # 32 seems to work best for fuzzyness? I'm still really not sure
                node.size = len(value)
            nodes.append(node)

        header.header_size = ((len(nodes) + 1) * len(rootnode)) + len(strings)
        header.data_offset = align(header.header_size + header.rootnode_offset, 64)
        rootnode.size = len(nodes) + 1

        for i in range(len(nodes)):
            if nodes[i].type == 0x0000:
                nodes[i].data_offset += header.data_offset

        fd = b''
        fd += header.pack()
        fd += rootnode.pack()
        for node in nodes:
            fd += node.pack()
        fd += strings
        fd += b'\x00' * (header.data_offset - header.rootnode_offset - header.header_size)
        fd += data

        return fd

    def _dumpDir(self, dir):
        if not os.path.isdir(dir):
            os.mkdir(dir)
        old = os.getcwd()
        os.chdir(dir)
        for item, data in self.files:
            if data is None:
                if not os.path.isdir(item):
                    os.mkdir(item)
            else:
                open(item, 'wb').write(data)
        os.chdir(old)

    def _loadDir(self, dir):
        try:
            self._tmpPath += ''
        except:
            self._tmpPath = ''
        old = os.getcwd()
        os.chdir(dir)
        entries = os.listdir('.')
        for entry in entries:
            if os.path.isdir(entry):
                self.files.append((self._tmpPath + entry, None))
                self._tmpPath += entry + '/'
                self._loadDir(entry)
            elif os.path.isfile(entry):
                data = open(entry, 'rb').read()
                self.files.append((self._tmpPath + entry, data))
        os.chdir(old)
        self._tmpPath = self._tmpPath[:self._tmpPath.find('/') + 1]

    def _load(self, data):
        offset = 0
        if isinstance(data, str):
            raise TypeError('This isn\'t Python 2 anymore. Only bytes, please.')

        for i in range(len(data)):
            header = self.U8Header()
            header.unpack(data[offset:offset + len(header)])
            if header.tag == b'U\xAA8-':
                break
            data = data[1:]
        offset += len(header)
        offset = header.rootnode_offset

        rootnode = self.U8Node()
        rootnode.unpack(data[offset:offset + len(rootnode)])
        offset += len(rootnode)

        nodes = []
        for i in range(rootnode.size - 1):
            node = self.U8Node()
            node.unpack(data[offset:offset + len(node)])
            offset += len(node)
            nodes.append(node)

        strings = data[offset:offset + header.data_offset - len(header) - (len(rootnode) * rootnode.size)]
        offset += len(strings)

        recursion = [rootnode.size, ]
        recursiondir = []
        counter = 0
        for node in nodes:
            counter += 1
            name = strings[node.name_offset:].split(b'\0', 1)[0].decode('latin-1')

            if node.type == 0x0100:  # folder
                recursion.append(node.size)
                recursiondir.append(name)
                self.files.append(('/'.join(recursiondir), None))

            elif node.type == 0:  # file
                self.files.append(
                    ('/'.join(recursiondir) + '/' + name, data[node.data_offset:node.data_offset + node.size]))
                offset += node.size

            else:  # unknown type -- wtf?
                pass

            sz = recursion.pop()
            if sz != counter + 1:
                recursion.append(sz)
            else:
                recursiondir.pop()

    def __str__(self):
        """
        Returns a representation of this U8 archive as a string
        """
        ret = ''
        for key, value in self.files:
            name = key.split('/')[-1]
            recursion = key.count('/')
            ret += '  ' * recursion
            if value is None:
                ret += '[' + name + ']'
            else:
                ret += name
            ret += '\n'
        return ret

    def __getitem__(self, key):
        """
        Returns the file requested when one indexes the archive
        """
        for item, val in self.files:
            if item == key:
                if val is not None:
                    return val
                else:
                    ret = []
                    for item2, val2 in self.files:
                        if item2.find(item) == 0:
                            ret.append(item2[len(item) + 1:])
                    return ret[1:]
        raise KeyError

    def __contains__(self, key):
        """
        Returns whether the archive contains a file with a key
        """
        for item, _ in self.files:
            if item == key:
                return True

        return False

    def __setitem__(self, key, val):
        """
        Handles the request to set a value to an index of the archive
        """
        for i in range(len(self.files)):
            if self.files[i][0] == key:
                self.files[i] = (self.files[i][0], val)
                return
        self.files.append((key, val))
