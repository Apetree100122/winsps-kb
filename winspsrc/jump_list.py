# -*- coding: utf-8 -*-
"""Windows Jump List files:
* .automaticDestinations-ms
* .customDestinations-ms
"""

import os

import pylnk
import pyolecf

from winspsrc import data_format
from winspsrc import data_range
from winspsrc import errors


class JumpListEntry(object):
  """Jump list entry.

  Attributes:
    identifier (str): identifier.
    lnk_file (pylnk.file): LNK file.
  """

  def __init__(self, identifier, file_object):
    """Initializes the jump list entry.

    Args:
      identifier (str): identifier.
      file_object (file): file-like object that contains the LNK file
          entry data.
    """
    super(JumpListEntry, self).__init__()
    self.identifier = identifier
    self.lnk_file = pylnk.file()
    self.lnk_file.open_file_object(file_object)

  def __del__(self):
    """Destroy the jump list entry."""
    self.lnk_file.close()
    self.lnk_file = None


class AutomaticDestinationsFile(data_format.BinaryDataFile):
  """Automatic Destinations Jump List (.automaticDestinations-ms) file."""

  # Using a class constant significantly speeds up the time required to load
  # the dtFabric definition file.
  _FABRIC = data_format.BinaryDataFile.ReadDefinitionFile('jump_list.yaml')

  def __init__(self):
    """Initializes an Automatic Destinations Jump List file."""
    super(AutomaticDestinationsFile, self).__init__()
    self._format_version = None
    self._olecf_file = None

  def _FormatIntegerAsPathSize(self, integer):
    """Formats an integer as a path size.

    Args:
      integer (int): integer.

    Returns:
      str: integer formatted as path size.
    """
    number_of_bytes = integer * 2
    return f'{integer:d} characters ({number_of_bytes:d} bytes)'

  def _ReadDestList(self, root_item):
    """Reads the DestList stream.

    Args:
      root_item (pyolecf.item): OLECF root item.

    Raises:
      ParseError: if the root item or DestList stream is missing.
    """
    if not root_item:
      raise errors.ParseError('Missing OLECF root item')

    olecf_item = root_item.get_sub_item_by_name('DestList')
    if not olecf_item:
      raise errors.ParseError('Missing DestList stream.')

    # The DestList stream can be of size 0 if the Jump List is empty.
    if olecf_item.size > 0:
      self._ReadDestListHeader(olecf_item)

      stream_offset = olecf_item.get_offset()
      stream_size = olecf_item.get_size()
      while stream_offset < stream_size:
        entry_size = self._ReadDestListEntry(olecf_item, stream_offset)
        stream_offset += entry_size

  def _ReadDestListEntry(self, olecf_item, stream_offset):
    """Reads a DestList stream entry.

    Args:
      olecf_item (pyolecf.item): OLECF item.
      stream_offset (int): stream offset of the entry.

    Returns:
      int: entry data size.

    Raises:
      ParseError: if the DestList stream entry cannot be read.
    """
    if self._format_version == 1:
      data_type_map = self._GetDataTypeMap('dest_list_entry_v1')
      description = 'dest list entry v1'

    elif self._format_version >= 2:
      data_type_map = self._GetDataTypeMap('dest_list_entry_v2')
      description = 'dest list entry v2'

    _, entry_data_size = self._ReadStructureFromFileObject(
        olecf_item, stream_offset, data_type_map, description)

    return entry_data_size

  def _ReadDestListHeader(self, olecf_item):
    """Reads the DestList stream header.

    Args:
      olecf_item (pyolecf.item): OLECF item.

    Raises:
      ParseError: if the DestList stream header cannot be read.
    """
    stream_offset = olecf_item.tell()
    data_type_map = self._GetDataTypeMap('dest_list_header')

    dest_list_header, _ = self._ReadStructureFromFileObject(
        olecf_item, stream_offset, data_type_map, 'dest list header')

    if dest_list_header.format_version not in (1, 2, 3, 4):
      raise errors.ParseError(
          f'Unsupported format version: {dest_list_header.format_version:d}')

    self._format_version = dest_list_header.format_version

  def Close(self):
    """Closes an Automatic Destinations Jump List file.

    Raises:
      IOError: if the file is not opened.
      OSError: if the file is not opened.
    """
    if self._olecf_file:
      self._olecf_file.close()
      self._olecf_file = None

    super(AutomaticDestinationsFile, self).Close()

  def GetJumpListEntries(self):
    """Retrieves jump list entries.

    Yields:
      JumpListEntry: a jump list entry.
    """
    for olecf_item in iter(self._olecf_file.root_item.sub_items):  # pylint: disable=no-member
      if olecf_item.name != 'DestList':
        yield JumpListEntry(olecf_item.name, olecf_item)

  def ReadFileObject(self, file_object):
    """Reads an Automatic Destinations Jump List file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file cannot be read.
    """
    olecf_file = pyolecf.file()
    olecf_file.open_file_object(file_object)

    self._ReadDestList(olecf_file.root_item)

    self._olecf_file = olecf_file


class CustomDestinationsFile(data_format.BinaryDataFile):
  """Custom Destinations Jump List (.customDestinations-ms) file."""

  # Using a class constant significantly speeds up the time required to load
  # the dtFabric definition file.
  _FABRIC = data_format.BinaryDataFile.ReadDefinitionFile('jump_list.yaml')

  _CATEGORY_FOOTER_SIGNATURE = b'\xab\xfb\xbf\xba'

  _LNK_GUID = (
      b'\x01\x14\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46')

  def __init__(self):
    """Initializes a Custom Destinations Jump List file."""
    super(CustomDestinationsFile, self).__init__()
    self._entries = []

  def _ReadCategoryFooter(self, file_object):
    """Reads the category footer.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the category footer cannot be read.
    """
    file_offset = file_object.tell()
    data_type_map = self._GetDataTypeMap('custom_category_footer')

    category_footer, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'category footer')

    if category_footer.signature != self._CATEGORY_FOOTER_SIGNATURE:
      raise errors.ParseError(
          f'Invalid footer signature at offset: 0x{file_offset:08x}.')

  def _ReadCategoryHeader(self, file_object, file_offset):
    """Reads a category header.

    Args:
      file_object (file): file-like object.
      file_offset (int): offset of the category header relative to the start of
          the file.

    Returns:
      tuple[custom_category_header, int]: category header and the number of
          bytes read.

    Raises:
      ParseError: if the category header cannot be read.
    """
    data_type_map = self._GetDataTypeMap('custom_category_header')

    category_header, bytes_read = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'category header')

    if category_header.category_type > 2:
      raise errors.ParseError(
          f'Unsupported category type: {category_header.category_type:d}.')

    file_offset += bytes_read
    total_bytes_read = bytes_read

    data_type_map = self._GetDataTypeMap(
        f'custom_category_header_type_{category_header.category_type:d}')

    category_header_value, bytes_read = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'category header values')

    if category_header.category_type in (0, 2):
      setattr(category_header, 'number_of_entries',
              category_header_value.number_of_entries)

    total_bytes_read += bytes_read

    return category_header, total_bytes_read

  def _ReadFileHeader(self, file_object):
    """Reads the file header.

    Args:
      file_object (file): file-like object.

    Returns:
      tuple[custom_file_header, int]: file header and the number of bytes read.

    Raises:
      ParseError: if the file header cannot be read.
    """
    data_type_map = self._GetDataTypeMap('custom_file_header')

    file_header, bytes_read = self._ReadStructureFromFileObject(
        file_object, 0, data_type_map, 'file header')

    return file_header, bytes_read

  def GetJumpListEntries(self):
    """Retrieves jump list entries.

    Yields:
      JumpListEntry: a jump list entry.

    Raises:
      ParseError: if the jump list entries cannot be read.
    """
    yield from self._entries

  def ReadFileObject(self, file_object):
    """Reads a Custom Destinations Jump List file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file cannot be read.
    """
    file_header, file_offset = self._ReadFileHeader(file_object)

    data_type_map = self._GetDataTypeMap('custom_entry_header')

    for _ in range(file_header.number_of_categories):
      category_header, bytes_read = self._ReadCategoryHeader(
          file_object, file_offset)

      file_offset += bytes_read

      number_of_entries = getattr(category_header, 'number_of_entries', 0)
      for entry_index in range(number_of_entries):
        if self._file_size - file_offset < 16:
          break

        try:
          entry_header, _ = self._ReadStructureFromFileObject(
              file_object, file_offset, data_type_map, 'entry header')

        except errors.ParseError as exception:
          raise errors.ParseError((
              f'Unable to parse entry: {entry_index:d}  at offset: '
              f'0x{file_offset:08x} with error: {exception!s}'))

        if entry_header.guid == self._LNK_GUID:
          file_offset += 16

          remaining_file_size = self._file_size - file_offset
          data_range_file_object = data_range.DataRange(
              file_object, data_offset=file_offset,
              data_size=remaining_file_size)

          jump_list_entry = JumpListEntry(
              f'0x{file_offset:08x}', data_range_file_object)

          self._entries.append(jump_list_entry)

          # We cannot trust the file size in the LNK data so we get the last
          # offset that was read instead. Because of DataRange the offset will
          # be relative to the start of the LNK data.
          entry_data_size = data_range_file_object.get_offset()

          file_offset += entry_data_size

        elif entry_header.guid[:4] != self._CATEGORY_FOOTER_SIGNATURE:
          raise errors.ParseError((
              f'Unsupported entry: {entry_index:d} at offset: '
              f'0x{file_offset:08x}'))

        file_object.seek(file_offset, os.SEEK_SET)

      self._ReadCategoryFooter(file_object)

      file_offset += 4
