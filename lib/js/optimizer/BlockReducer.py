#
# JavaScript Tools - Optimizes if-statements for reduced compression size
# Copyright 2010 Sebastian Werner
#

from js.parser.Node import Node
from js.Compressor import compress
from js.parser.Lang import expressionOrder, expressions
import logging

__all__ = ["optimize"]

def optimize(node, level=0):
    # Process from inside to outside
    for child in node:
        optimize(child, level+1)
        
        
    # Remove unneeded parens
    if getattr(node, "parenthesized", False) and node.type in expressions:
        fixParens(node)
    
    
    # Unwrap blocks
    if node.type == "block":
        if node.parent.type in ("try", "catch", "finally"):
            # print("Omit unwrapping of block (try/catch/finally) at #%s" % level)
            pass
        elif len(node) == 0:
            # print("Replace empty block #%s" % level)
            node.parent.replace(node, Node(node.tokenizer, "semicolon"))
        elif len(node) == 1:
            if node.parent.type == "if" and containsIf(node):
                # print("Omit unwrapping of block (cascaded if blocks) at #%s" % level)
                pass
            else:
                # print("Unwrap block at #%s" % level)
                node.parent.replace(node, node[0])
            
            
    # Process all if-statements
    if node.type == "if":
        condition = node.condition
        thenPart = node.thenPart
        elsePart = getattr(node, "elsePart", None)
        
        # Optimize using hook operator
        if elsePart and thenPart.type == "return" and elsePart.type == "return":
            # Combine return statement
            # print("Merge return at #%s" % level)
            replacement = createReturn(createHook(condition, thenPart.value, elsePart.value))
            node.parent.replace(node, replacement)
            return

        # Check whether if-part ends with a return statement. Then
        # We do not need a else statement here and just can wrap the whole content
        # of the else block inside the parent
        if elsePart and endsWithReturnOrThrow(thenPart):
            ifIndex = node.parent.index(node)+1

            if elsePart.type == "if":
                node.parent.insert(ifIndex, elsePart)

                # Reset elsePart variable as it is now cleaned up
                elsePart = None
                                
            elif elsePart.type == "block":
                for child in reversed(elsePart):
                    node.parent.insert(ifIndex, child)

                # Remove else block from if statement
                node.remove(elsePart)
            
                # Reset elsePart variable as it is now cleaned up
                elsePart = None

        # Optimize using "AND" or "OR" operators
        # Combine multiple semicolon statements into one semicolon statement using an "comma" expression
        thenPart = combineToCommaExpression(thenPart, level)
        elsePart = combineToCommaExpression(elsePart, level)
        
        # Optimize else-if
        if elsePart:
            if thenPart.type == "semicolon" and elsePart.type == "semicolon":
                # Combine two assignments or expressions
                thenExpression = getattr(thenPart, "expression", None)
                elseExpression = getattr(elsePart, "expression", None)
                if thenExpression and elseExpression:
                    replacement = combineAssignments(condition, thenExpression, elseExpression) or combineExpressions(condition, thenExpression, elseExpression)
                    if replacement:
                        # print("Merge assignment/expression at #%s" % level)
                        node.parent.replace(node, replacement)
                        
        # Optimize simple if
        elif thenPart.type == "semicolon":
            compactIf(node, thenPart, condition)




def endsWithReturnOrThrow(node):
    if node.type in ("return", "throw"):
        return True
        
    elif node.type == "block":
        length = len(node)
        return length > 0 and node[length-1].type in ("return", "throw")
        
    return False



def fixParens(node):
    parent = node.parent
    
    if node.type in expressions and parent.type == "return":
        node.parenthesized = False

    elif node.type == "function" and parent.type == "call":
        # Ignore for direct execution functions
        pass
        
    elif parent.type in expressions:
        prio = expressionOrder[node.type]
        parentPrio = expressionOrder[node.parent.type]
        needsParens = prio < parentPrio
        
        # Fix minor priority issue in hook statements. They are a little bit special. 
        # In their condition part, assignments have lower priority than the hook, in 
        # the action parts it's the other way around.
        if parent.type == "hook" and node.type == "assign":
            needsParens = node.rel == "condition"

        node.parenthesized = needsParens
        
    elif node.type in expressions and getattr(node, "rel") == "condition":
        # inside a condition e.g. while(condition) or for(;condition;) we do not need
        # parens aroudn an expression
        node.parenthesized = False



def combineToCommaExpression(node, level):
    if node == None or node.type != "block":
        return node
        
    for child in node:
        if child.type != "semicolon":
            return node
    
    comma = Node(node.tokenizer, "comma")
    
    for child in list(node):
        # Ignore empty semicolons
        if hasattr(child, "expression"):
            comma.append(child.expression)
            
    semicolon = Node(node.tokenizer, "semicolon")
    semicolon.append(comma, "expression")
    
    parent = node.parent
    parent.replace(node, semicolon)
    
    # print("Combine to comma expression at: #%s" % level)
    return semicolon
        


def compactIf(node, thenPart, condition):
    thenExpression = getattr(thenPart, "expression", None)
    if not thenExpression:
        # Empty semicolon statement => translate if into semicolon statement
        node.remove(condition)
        node.remove(node.thenPart)
        node.append(condition, "expression")
        node.type = "semicolon"

    else:
        # Has expression => Translate IF using a AND or OR operator
        if condition.type == "not":
            replacement = Node(thenPart.tokenizer, "or")
            condition = condition[0]
        else:
            replacement = Node(thenPart.tokenizer, "and")

        replacement.append(condition)
        replacement.append(thenExpression)

        thenPart.append(replacement, "expression")

        fixParens(thenExpression)
        fixParens(condition)    
        
        node.parent.replace(node, thenPart)


def containsIf(node):
    """ helper for block removal optimization """
    if node.type == "if":
        return True

    for child in node:
        if containsIf(child):
            return True

    return False


def combineAssignments(condition, thenExpression, elseExpression):
    if thenExpression.type == "assign" and elseExpression.type == "assign":
        operator = getattr(thenExpression, "assignOp", None)
        if operator == getattr(elseExpression, "assignOp", None):
            if compress(thenExpression[0]) == compress(elseExpression[0]):
                hook = createHook(condition, thenExpression[1], elseExpression[1])
                fixParens(condition)
                fixParens(hook.thenPart)
                fixParens(hook.elsePart)
                thenExpression.append(hook)
                return thenExpression.parent


def combineExpressions(condition, thenExpression, elseExpression):
    hook = createHook(condition, thenExpression, elseExpression)
    semicolon = Node(condition.tokenizer, "semicolon")
    semicolon.append(hook, "expression")
    
    fixParens(condition)
    fixParens(thenExpression)
    fixParens(elseExpression)
    
    return semicolon


def createReturn(value):
    ret = Node(value.tokenizer, "return")
    ret.append(value, "value")
    return ret


def createHook(condition, thenPart, elsePart):
    hook = Node(condition.tokenizer, "hook")
    hook.append(condition, "condition")
    hook.append(thenPart, "thenPart")
    hook.append(elsePart, "elsePart")
    return hook
    