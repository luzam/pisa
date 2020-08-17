# -*- coding: ISO-8859-1 -*-

# Copyright 2010 Dirk Holtwick, holtwick.it
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
__reversion__ = "$Revision: 20 $"
__author__ = "$Author: holtwick $"
__date__ = "$Date: 2007-10-09 12:58:24 +0200 (Di, 09 Okt 2007) $"

import pprint
import copy
import types
import re
import os
import os.path

import html5lib
from html5lib import treebuilders, serializer, treewalkers, inputstream
from xml.dom import Node
import xml.dom.minidom

from .pisa_default import *
from .pisa_util import *
from .pisa_tags import *
from .pisa_tables import *

import sx.w3c.css as css
import sx.w3c.cssDOMElementInterface as cssDOMElementInterface

import logging
log = logging.getLogger("ho.pisa")

rxhttpstrip = re.compile("https?://[^/]+(.*)", re.M | re.I)

class AttrContainer(dict):
      
    def __getattr__(self, name):       
        try:
            return dict.__getattr__(self, name)            
        except:
            return self[name]

def pisaGetAttributes(c, tag, attributes):
    global TAGS

    attrs = {}
    if attributes:
        for k, v in attributes.items():
            try:
                attrs[str(k)] = str(v) # XXX no Unicode! Reportlab fails with template names
            except:
                attrs[k] = v
                
    nattrs = {}
    if tag in TAGS:        
        block, adef = TAGS[tag]
        adef["id"] = STRING
        # print block, adef
        for k, v in adef.items():                
            nattrs[k] = None
            # print k, v
            # defaults, wenn vorhanden
            if type(v) == tuple:                
                if v[1] == MUST:
                    if k not in attrs:
                        log.warn(c.warning("Attribute '%s' must be set!", k))
                        nattrs[k] = None
                        continue
                nv = attrs.get(k, v[1])                    
                dfl = v[1]
                v = v[0]
            else:
                nv = attrs.get(k, None)
                dfl = None               
            try:
                if nv is not None:
                    
                    if type(v) == list:
                        nv = nv.strip().lower()
                        if nv not in v:
                            #~ raise PML_EXCEPTION, "attribute '%s' of wrong value, allowed is one of: %s" % (k, repr(v))
                            log.warn(c.warning("Attribute '%s' of wrong value, allowed is one of: %s", k, repr(v)))
                            nv = dfl

                    elif v == BOOL:
                        nv = nv.strip().lower()
                        nv = nv in ("1", "y", "yes", "true", str(k))

                    elif v == SIZE:
                        try:
                            nv = getSize(nv)
                        except:
                            log.warn(c.warning("Attribute '%s' expects a size value", k))

                    elif v == BOX:
                        nv = getBox(nv, c.pageSize)

                    elif v == POS:
                        nv = getPos(nv, c.pageSize)

                    elif v == INT:
                        nv = int(nv)

                    elif v == COLOR:
                        nv = getColor(nv)
                    
                    elif v == FILE:
                        nv = c.getFile(nv)
                                                
                    elif v == FONT:
                        nv = c.getFontName(nv)

                    nattrs[k] = nv

            #for k in attrs.keys():
            #    if not nattrs.has_key(k):
            #        c.warning("attribute '%s' for tag <%s> not supported" % (k, tag))

            except Exception as e:
                log.exception(c.error("Tag handling"))

    #else:
    #    c.warning("tag <%s> is not supported" % tag)
   
    return AttrContainer(nattrs)

attrNames = '''
    color
    font-family 
    font-size 
    font-weight
    font-style
    text-decoration
    line-height
    background-color
    display
    margin-left
    margin-right
    margin-top
    margin-bottom
    padding-left
    padding-right
    padding-top
    padding-bottom
    border-top-color
    border-top-style
    border-top-width
    border-bottom-color
    border-bottom-style
    border-bottom-width
    border-left-color
    border-left-style
    border-left-width
    border-right-color
    border-right-style
    border-right-width
    text-align
    vertical-align
    width
    height
    zoom
    page-break-after
    page-break-before
    list-style-type
    list-style-image
    white-space
    text-indent
    -pdf-page-break
    -pdf-frame-break
    -pdf-next-page
    -pdf-keep-with-next
    -pdf-outline
    -pdf-outline-level
    -pdf-outline-open
    -pdf-line-spacing
    -pdf-keep-in-frame-mode    
    '''.strip().split()
 
def getCSSAttr(self, cssCascade, attrName, default=NotImplemented):
    if attrName in self.cssAttrs:
        return self.cssAttrs[attrName]
    
    try:
        result = cssCascade.findStyleFor(self.cssElement, attrName, default)
    except LookupError:
        result = None        

    # XXX Workaround for inline styles
    try:
        style = self.cssStyle
    except:
        style = self.cssStyle = cssCascade.parser.parseInline(self.cssElement.getStyleAttr() or '')[0]        
    if attrName in style:
        result = style[attrName]        
        
    if result == 'inherit':
        if hasattr(self.parentNode, 'getCSSAttr'):
            result = self.parentNode.getCSSAttr(cssCascade, attrName, default)
        elif default is not NotImplemented:
            return default
        else:
            raise LookupError("Could not find inherited CSS attribute value for '%s'" % (attrName,))
    
    if result is not None:
        self.cssAttrs[attrName] = result
    return result

xml.dom.minidom.Element.getCSSAttr = getCSSAttr

def CSSCollect(node, c):
    #node.cssAttrs = {}
    #return node.cssAttrs
    if c.css:
        node.cssElement = cssDOMElementInterface.CSSDOMElementInterface(node)
        node.cssAttrs = {}
        # node.cssElement.onCSSParserVisit(c.cssCascade.parser)
        cssAttrMap = {}
        for cssAttrName in attrNames:
            try:
                cssAttrMap[cssAttrName] = node.getCSSAttr(c.cssCascade, cssAttrName)
            #except LookupError:
            #    pass
            except Exception:
                log.debug("CSS error '%s'", cssAttrName, exc_info=1)        
    return node.cssAttrs

def CSS2Frag(c, kw, isBlock):    
    # COLORS
    if "color" in c.cssAttr:
        c.frag.textColor = getColor(c.cssAttr["color"])    
    if "background-color" in c.cssAttr:
        c.frag.backColor = getColor(c.cssAttr["background-color"])
    # FONT SIZE, STYLE, WEIGHT    
    if "font-family" in c.cssAttr:
        c.frag.fontName = c.getFontName(c.cssAttr["font-family"])    
    if "font-size" in c.cssAttr:
        # XXX inherit
        c.frag.fontSize = max(getSize("".join(c.cssAttr["font-size"]), c.frag.fontSize, c.baseFontSize), 1.0)    
    if "line-height" in c.cssAttr:
        leading = "".join(c.cssAttr["line-height"])
        c.frag.leading = getSize(leading, c.frag.fontSize)
        c.frag.leadingSource = leading
    else:
        c.frag.leading = getSize(c.frag.leadingSource, c.frag.fontSize)
    if "-pdf-line-spacing" in c.cssAttr:         
        c.frag.leadingSpace = getSize("".join(c.cssAttr["-pdf-line-spacing"]))    
        # print "line-spacing", c.cssAttr["-pdf-line-spacing"], c.frag.leading                            
    if "font-weight" in c.cssAttr:
        value = c.cssAttr["font-weight"].lower()
        if value in ("bold", "bolder", "500", "600", "700", "800", "900"):
            c.frag.bold = 1
        else:
            c.frag.bold = 0
    for value in toList(c.cssAttr.get("text-decoration", "")):
        if "underline" in value:
            c.frag.underline = 1
        if "line-through" in value:
            c.frag.strike = 1
        if "none" in value:
            c.frag.underline = 0
            c.frag.strike = 0
    if "font-style" in c.cssAttr:
        value = c.cssAttr["font-style"].lower()
        if value in ("italic", "oblique"):
            c.frag.italic = 1
        else:
            c.frag.italic = 0
    if "white-space" in c.cssAttr:
        # normal | pre | nowrap
        c.frag.whiteSpace = str(c.cssAttr["white-space"]).lower()
    # ALIGN & VALIGN
    if "text-align" in c.cssAttr:
        c.frag.alignment = getAlign(c.cssAttr["text-align"])
    if "vertical-align" in c.cssAttr:
        c.frag.vAlign = c.cssAttr["vertical-align"]
    # HEIGHT & WIDTH
    if "height" in c.cssAttr:
        c.frag.height = "".join(toList(c.cssAttr["height"])) # XXX Relative is not correct!
        if c.frag.height in ("auto",):
            c.frag.height = None
    if "width" in c.cssAttr:
        # print c.cssAttr["width"]
        c.frag.width = "".join(toList(c.cssAttr["width"])) # XXX Relative is not correct!
        if c.frag.width in ("auto",):
            c.frag.width = None
    # ZOOM
    if "zoom" in c.cssAttr:
        # print c.cssAttr["width"]
        zoom = "".join(toList(c.cssAttr["zoom"])) # XXX Relative is not correct!
        if zoom.endswith("%"):
            zoom = float(zoom[: - 1]) / 100.0
        c.frag.zoom = float(zoom)
    # MARGINS & LIST INDENT, STYLE
    if isBlock:
        if "margin-top" in c.cssAttr:
            c.frag.spaceBefore = getSize(c.cssAttr["margin-top"], c.frag.fontSize)
        if "margin-bottom" in c.cssAttr:
            c.frag.spaceAfter = getSize(c.cssAttr["margin-bottom"], c.frag.fontSize)
        if "margin-left" in c.cssAttr:
            c.frag.bulletIndent = kw["margin-left"] # For lists
            kw["margin-left"] += getSize(c.cssAttr["margin-left"], c.frag.fontSize)
            c.frag.leftIndent = kw["margin-left"]
        # print "MARGIN LEFT", kw["margin-left"], c.frag.bulletIndent
        if "margin-right" in c.cssAttr:
            kw["margin-right"] += getSize(c.cssAttr["margin-right"], c.frag.fontSize)
            c.frag.rightIndent = kw["margin-right"]
        # print c.frag.rightIndent
        if "text-indent" in c.cssAttr:
            c.frag.firstLineIndent = getSize(c.cssAttr["text-indent"], c.frag.fontSize)
        if "list-style-type" in c.cssAttr:
            c.frag.listStyleType = str(c.cssAttr["list-style-type"]).lower()
        if "list-style-image" in c.cssAttr:
            c.frag.listStyleImage = c.getFile(c.cssAttr["list-style-image"])
    # PADDINGS
    if isBlock:
        if "padding-top" in c.cssAttr:
            c.frag.paddingTop = getSize(c.cssAttr["padding-top"], c.frag.fontSize)
        if "padding-bottom" in c.cssAttr:
            c.frag.paddingBottom = getSize(c.cssAttr["padding-bottom"], c.frag.fontSize)
        if "padding-left" in c.cssAttr:
            c.frag.paddingLeft = getSize(c.cssAttr["padding-left"], c.frag.fontSize)
        if "padding-right" in c.cssAttr:
            c.frag.paddingRight = getSize(c.cssAttr["padding-right"], c.frag.fontSize)
    # BORDERS
    if isBlock:
        if "border-top-width" in c.cssAttr:
            # log.debug(c.cssAttr["border-top-width"])
            c.frag.borderTopWidth = getSize(c.cssAttr["border-top-width"], c.frag.fontSize)
        if "border-bottom-width" in c.cssAttr:
            c.frag.borderBottomWidth = getSize(c.cssAttr["border-bottom-width"], c.frag.fontSize)
        if "border-left-width" in c.cssAttr:
            c.frag.borderLeftWidth = getSize(c.cssAttr["border-left-width"], c.frag.fontSize)
        if "border-right-width" in c.cssAttr:
            c.frag.borderRightWidth = getSize(c.cssAttr["border-right-width"], c.frag.fontSize)
        if "border-top-style" in c.cssAttr:
            c.frag.borderTopStyle = c.cssAttr["border-top-style"]
        if "border-bottom-style" in c.cssAttr:
            c.frag.borderBottomStyle = c.cssAttr["border-bottom-style"]
        if "border-left-style" in c.cssAttr:
            c.frag.borderLeftStyle = c.cssAttr["border-left-style"]
        if "border-right-style" in c.cssAttr:
            c.frag.borderRightStyle = c.cssAttr["border-right-style"]
        if "border-top-color" in c.cssAttr:
            c.frag.borderTopColor = getColor(c.cssAttr["border-top-color"])
        if "border-bottom-color" in c.cssAttr:
            c.frag.borderBottomColor = getColor(c.cssAttr["border-bottom-color"])
        if "border-left-color" in c.cssAttr:
            c.frag.borderLeftColor = getColor(c.cssAttr["border-left-color"])
        if "border-right-color" in c.cssAttr:
            c.frag.borderRightColor = getColor(c.cssAttr["border-right-color"])

def pisaPreLoop(node, c, collect=False):
    """
    Collect all CSS definitions 
    """
    
    data = u""    
    if node.nodeType == Node.TEXT_NODE and collect:
        data = node.data
        
    elif node.nodeType == Node.ELEMENT_NODE:
        name = node.tagName.lower()

        # print name, node.attributes.items()
        if name in ("style", "link"):
            attr = pisaGetAttributes(c, name, node.attributes)
            # print " ", attr
            media = [x.strip() for x in attr.media.lower().split(",") if x.strip()]
            # print repr(media)
            
            if (attr.get("type", "").lower() in ("", "text/css") and (
                not media or                
                "all" in media or
                "print" in media or
                "pdf" in media)):  
    
                if name == "style":
                    for node in node.childNodes:
                        data += pisaPreLoop(node, c, collect=True)                    
                    c.addCSS(data)                        
                    return u""
                    #collect = True
                                
                if name == "link" and attr.href and attr.rel.lower() == "stylesheet":
                    # print "CSS LINK", attr
                    c.addCSS('\n@import "%s" %s;' % (attr.href, ",".join(media)))
                    # c.addCSS(unicode(file(attr.href, "rb").read(), attr.charset))

    #else:
    #    print node.nodeType

    for node in node.childNodes:        
        result = pisaPreLoop(node, c, collect=collect)
        if collect:
            data += result
        
    return data

def pisaLoop(node, c, path=[], **kw):

    # Initialize KW
    if not kw:
        kw = {
            "margin-top": 0,
            "margin-bottom": 0,
            "margin-left": 0,
            "margin-right": 0,
            }
    else:
        kw = copy.copy(kw)
        
    indent = len(path) * "  "

    # TEXT
    if node.nodeType == Node.TEXT_NODE:
        # print indent, "#", repr(node.data) #, c.frag
        c.addFrag(node.data)
        # c.text.append(node.value)
       
    # ELEMENT
    elif node.nodeType == Node.ELEMENT_NODE:  
        
        node.tagName = node.tagName.replace(":", "").lower()
        
        if node.tagName in ("style", "script"):
            return
        
        path = copy.copy(path) + [node.tagName]
        
        # Prepare attributes        
        attr = pisaGetAttributes(c, node.tagName, node.attributes)        
        # log.debug(indent + "<%s %s>" % (node.tagName, attr) + repr(node.attributes.items())) #, path
        
        # Calculate styles                
        c.cssAttr = CSSCollect(node, c)
        c.node = node

        # Block?    
        PAGE_BREAK = 1
        PAGE_BREAK_RIGHT = 2
        PAGE_BREAK_LEFT = 3

        pageBreakAfter = False
        frameBreakAfter = False
        display = c.cssAttr.get("display", "inline").lower()
        # print indent, node.tagName, display, c.cssAttr.get("background-color", None), attr
        isBlock = (display == "block")
        if isBlock:
            c.addPara()

            # Page break by CSS
            if "-pdf-next-page" in c.cssAttr:                 
                c.addStory(NextPageTemplate(str(c.cssAttr["-pdf-next-page"])))
            if "-pdf-page-break" in c.cssAttr:
                if str(c.cssAttr["-pdf-page-break"]).lower() == "before":
                    c.addStory(PageBreak()) 
            if "-pdf-frame-break" in c.cssAttr: 
                if str(c.cssAttr["-pdf-frame-break"]).lower() == "before":
                    c.addStory(FrameBreak()) 
                if str(c.cssAttr["-pdf-frame-break"]).lower() == "after":
                    frameBreakAfter = True
            if "page-break-before" in c.cssAttr:            
                if str(c.cssAttr["page-break-before"]).lower() == "always":
                    c.addStory(PageBreak()) 
                if str(c.cssAttr["page-break-before"]).lower() == "right":
                    c.addStory(PageBreak()) 
                    c.addStory(PmlRightPageBreak())
                if str(c.cssAttr["page-break-before"]).lower() == "left":
                    c.addStory(PageBreak()) 
                    c.addStory(PmlLeftPageBreak())
            if "page-break-after" in c.cssAttr:            
                if str(c.cssAttr["page-break-after"]).lower() == "always":
                    pageBreakAfter = PAGE_BREAK
                if str(c.cssAttr["page-break-after"]).lower() == "right":
                    pageBreakAfter = PAGE_BREAK_RIGHT
                if str(c.cssAttr["page-break-after"]).lower() == "left":
                    pageBreakAfter = PAGE_BREAK_LEFT
            
        if display == "none":
            # print "none!"
            return
        
        # Translate CSS to frags 

        # Save previous frag styles
        c.pushFrag()
        
        # Map styles to Reportlab fragment properties
        CSS2Frag(c, kw, isBlock) 
                          
        # EXTRAS
        if "-pdf-keep-with-next" in c.cssAttr:
            c.frag.keepWithNext = getBool(c.cssAttr["-pdf-keep-with-next"])
        if "-pdf-outline" in c.cssAttr:
            c.frag.outline = getBool(c.cssAttr["-pdf-outline"])
        if "-pdf-outline-level" in c.cssAttr:
            c.frag.outlineLevel = int(c.cssAttr["-pdf-outline-level"])
        if "-pdf-outline-open" in c.cssAttr:
            c.frag.outlineOpen = getBool(c.cssAttr["-pdf-outline-open"])
        #if c.cssAttr.has_key("-pdf-keep-in-frame-max-width"):
        #    c.frag.keepInFrameMaxWidth = getSize("".join(c.cssAttr["-pdf-keep-in-frame-max-width"]))
        #if c.cssAttr.has_key("-pdf-keep-in-frame-max-height"):
        #    c.frag.keepInFrameMaxHeight = getSize("".join(c.cssAttr["-pdf-keep-in-frame-max-height"]))
        if "-pdf-keep-in-frame-mode" in c.cssAttr:
            value = str(c.cssAttr["-pdf-keep-in-frame-mode"]).strip().lower()
            if value not in ("shrink", "error", "overflow", "shrink", "truncate"):
                value = None
            c.frag.keepInFrameMode = value
                
        # BEGIN tag
        klass = globals().get("pisaTag%s" % node.tagName.replace(":", "").upper(), None)
        obj = None      

        # Static block
        elementId = attr.get("id", None)             
        staticFrame = c.frameStatic.get(elementId, None)
        if staticFrame:
            c.frag.insideStaticFrame += 1
            oldStory = c.swapStory()
                  
        # Tag specific operations
        if klass is not None:        
            obj = klass(node, attr)
            obj.start(c)
            
        # Visit child nodes
        c.fragBlock = fragBlock = copy.copy(c.frag)        
        for nnode in node.childNodes:
            pisaLoop(nnode, c, path, **kw)        
        c.fragBlock = fragBlock
                            
        # END tag
        if obj:
            obj.end(c)

        # Block?
        if isBlock:
            c.addPara()

            # XXX Buggy!

            # Page break by CSS
            if pageBreakAfter:
                c.addStory(PageBreak()) 
                if pageBreakAfter == PAGE_BREAK_RIGHT:
                    c.addStory(PmlRightPageBreak())
                if pageBreakAfter == PAGE_BREAK_LEFT:
                    c.addStory(PmlLeftPageBreak())
            if frameBreakAfter:                
                c.addStory(FrameBreak()) 

        # Static block, END
        if staticFrame:
            c.addPara()
            for frame in staticFrame:
                frame.pisaStaticStory = c.story            
            c.swapStory(oldStory)
            c.frag.insideStaticFrame -= 1
            
        # c.debug(1, indent, "</%s>" % (node.tagName))
        
        # Reset frag style                   
        c.pullFrag()                                    

    # Unknown or not handled
    else:
        # c.debug(1, indent, "???", node, node.nodeType, repr(node))
        # Loop over children
        for node in node.childNodes:
            pisaLoop(node, c, path, **kw)

def pisaParser(src, c, default_css="", xhtml=False, encoding=None, xml_output=None):
    """    
    - Parse HTML and get miniDOM
    - Extract CSS informations, add default CSS, parse CSS
    - Handle the document DOM itself and build reportlab story
    - Return Context object     
    """
    
    if xhtml:
        parser = html5lib.XHTMLParser(tree=treebuilders.getTreeBuilder("dom"))
    else:
        parser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder("dom"))

    if type(src) in (str,):
        if type(src) is str:
            encoding = "utf8"
            src = src.encode(encoding)
        src = pisaTempFile(src, capacity=c.capacity)    

    # Test for the restrictions of html5lib
    if encoding:
        # Workaround for html5lib<0.11.1        
        if hasattr(inputstream, "isValidEncoding"):
            if encoding.strip().lower() == "utf8":
                encoding = "utf-8"
            if not inputstream.isValidEncoding(encoding):
                log.error("%r is not a valid encoding e.g. 'utf8' is not valid but 'utf-8' is!", encoding)
        else:
             if inputstream.codecName(encoding) is None:
                 log.error("%r is not a valid encoding", encoding)
    
    document = parser.parse(
        src,
        encoding=encoding)
        
    if xml_output:        
        xml_output.write(document.toprettyxml(encoding="utf8"))    

    if default_css:
        c.addCSS(default_css)
        
    pisaPreLoop(document, c)    
    #try:
    c.parseCSS()        
    #except:
    #    c.cssText = DEFAULT_CSS
    #    c.parseCSS()        
    # c.debug(9, pprint.pformat(c.css))        
    pisaLoop(document, c)
    return c

# Shortcuts

HTML2PDF = pisaParser

def XHTML2PDF(*a, **kw):
    kw["xhtml"] = True
    return HTML2PDF(*a, **kw)  

XML2PDF = XHTML2PDF
