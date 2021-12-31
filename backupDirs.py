import logging
import logging.config
import yaml
# !/usr/bin/env python3

import sys, shutil, readchar, traceback
import hashlib, os
from pathlib import PurePath, Path
from itertools import filterfalse


def printExceptionDetails(inst, message, object):
    if message:
        logger.error("Error processing '{}':".format(message, object))

    logger.error(type(inst))  # the exception instance
    logger.error(inst.args)  # arguments stored in .args
    logger.error(inst)  # __str__ allows args to be printed directly, but may be overridden in exception subclasses


def writeToMD5File(md5File, md5hashes):
    with open(md5File, "a+") as afile:
        for md5hash in md5hashes:
            afile.write("{} *.\\{}\n".format(md5hash[0], md5hash[1]))


def getHashofDirs(directory, verbose=0, silent=0):
    BLOCKSIZE = 65536
    hasher = hashlib.md5()
    if not os.path.exists(directory):
        return -1

    try:
        md5hashes = []
        for root, dirs, files in os.walk(directory):
            for fileName in files:
                hasherFile = hashlib.md5()
                if verbose > 1:
                    logger.debug("Hashing: '{}'".format(root + os.path.sep + fileName))
                filepath = os.path.join(root, fileName)
                with open(filepath, "rb") as afile:
                    buf = afile.read(BLOCKSIZE)
                    while len(buf) > 0:
                        hasherFile.update(buf)
                        buf = afile.read(BLOCKSIZE)
                md5hashes.append((hasherFile.hexdigest(), os.path.splitdrive(filepath)[1]))
                hasher.update(hasherFile.hexdigest().encode("UTF-8"))

    except Exception as inst:
        # Print the stack traceback
        traceback.print_exc()
        return -2

    if verbose > 0:
        logger.debug("Hash '{}':'{}'".format(directory, hasher.hexdigest()))

    return hasher.hexdigest(), md5hashes


def removeOldTargets(baseSourceFile, baseTargetPath, verbose=0, silent=0):
    selectedDirs = []
    with open(baseSourceFile, 'r') as f:
        item = f.read()
        selectedDirs = list(filter(lambda k: k.startswith('-'), item.split("\n")))

    selectedDirs.sort()
    selDirs = []
    for item in selectedDirs:
        selDirs.append(item.lstrip('- '))

    origSelDirs = selDirs.copy()

    # logger.debug("selDirs: '{}'".format(selDirs))

    oldTargetsDeleted = []
    oldTargetsNotDeleted = []
    oldTargetsNotFound = selDirs.copy()
    # Remove listed directories in file
    ########################################################
    baseTargetPathConcrete = Path(baseTargetPath)
    for item in baseTargetPathConcrete.iterdir():
        if verbose > 1:
            logger.debug("Item.name: '{}', ItemType: '{}'".format(item.name, type(item)))
        if item.is_dir() and item.name in selDirs:
            try:
                oldTargetsNotFound.remove(item.name)
                userResponse = ''
                while userResponse != 'S' and userResponse != 'N' and userResponse != 'L':
                    logger.info("Do you want to remove '{}' (S/N)?".format(item.name))
                    if silent == 0:
                        userResponse = readchar.readkey().upper()
                    else:
                        userResponse = 'S'
                if userResponse.capitalize() == 'S':
                    logger.info("DirDeletion: '{}'".format(item.name.strip()))
                    #            shutil.move(item, "{} (removed)".format(str(item).strip()))
                    shutil.rmtree(item)
                    selDirs.remove(item.name)
                    oldTargetsDeleted.append(item.name)
            except Exception as inst:
                printExceptionDetails(inst, "Error removing", item)

    logger.info("Complete list:{}".format(origSelDirs))
    logger.info("Not found:{}".format(selDirs))
    oldTargetsNotDeleted = list(filterfalse(oldTargetsNotFound.__contains__, selDirs))

    return oldTargetsDeleted, oldTargetsNotDeleted, oldTargetsNotFound


def copyNewTargets(baseSourcePath, targetPath, targetMD5File, verbose=0, silent=0):
    deletedSources = []
    copiedSources = []
    copyFailed = []
    notCopied = []
    # Copy directories from source path to target path
    ########################################################
    baseSourcePathConcrete = Path(baseSourcePath)
    for item in baseSourcePathConcrete.iterdir():
        #  logger.debug("ItemType: '{}'".format(type(item)))
        if item.is_dir():
            try:
                userResponse = ''
                while userResponse != 'S' and userResponse != 'N' and userResponse != 'L':
                    logger.info("Do you want to copy '{}' (S/N)?".format(item.name))
                    if silent == 0:
                        userResponse = readchar.readkey().upper()
                    else:
                        userResponse = 'S'
                if userResponse.capitalize() == 'S':
                    logger.info("Calculating source hash...")
                    hashSource, md5hashes = getHashofDirs(item, verbose)
                    logger.info("Copying: '{}'".format(item.name.strip()))
                    shutil.copytree(item, PurePath(targetPath, item.name))
                    logger.info("Calculating target hash...")
                    hashTarget, md5hashes = getHashofDirs(PurePath(targetPath, item.name), verbose)
                    logger.debug("hashSource={},hashTarget={}".format(hashSource, hashTarget))
                    copiedSources.append(item.name)
                    if hashSource == hashTarget:
                        writeToMD5File(targetMD5File, md5hashes)
                        logger.info("Hash copy matches, proceding to delete source directory '{}' (S/N)".format(item))
                        if silent == 0:
                            userResponse = readchar.readkey().upper()
                        else:
                            userResponse = 'S'
                        if userResponse.capitalize() == 'S':
                            shutil.rmtree(item)
                            deletedSources.append(item.name)
                            logger.info("Deleted source directory '{}'".format(item))
                    else:
                        copyFailed(item.name)
                        logger.error("Hash copy doesn't match the source")
                else:
                    notCopied.append(item.name)
                    logger.info("Not copied '{}'".format(item.name))
            except Exception as inst:
                printExceptionDetails(inst, "Error copying", item)
                logger.error("inst:{}".format(inst))
                copyFailed.append((item.name, inst.args[0]))

    return deletedSources, copiedSources, copiedSources, notCopied, copyFailed


def init_logger():
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    return logging.getLogger()  # "web_scraper")


global logger


def main(argv):
    global logger
    logger = init_logger()

    verbose = 2
    silent = 1
    sourceFile = "notas.txt"
    targetMD5File = "checksums.md5"

    if len(sys.argv) == 4:
        sourcePath = sys.argv[1]
        targetPathBase = sys.argv[2]
        targetPath = sys.argv[3]
    else:
        sourcePath = "_source"
        targetPathBase = "E:\prog\python\pruebas"
        targetPath = "juegos"

    logger.warning("sourcePath={},targetPathBase={},targetPath={}".format(sourcePath, targetPathBase, targetPath))

    baseTargetPath = PurePath(targetPathBase, targetPath)
    baseTargetMD5File = PurePath(targetPathBase, targetMD5File)
    baseSourcePath = PurePath(sourcePath)
    baseSourceFile = PurePath(sourcePath, sourceFile)

    # dirHash, md5hashes = getHashofDirs("D:\_juegos\__nuevo__\_J2\Space Rangers HD - A War Apart v2.1.2424 [FitGirl]", verbose)
    # print("dirHash:{}".format(dirHash))
    # print("md5hashes:{}".format(md5hashes))
    # writeToMD5File(targetMD5File, md5hashes)
    # oldTargetsDeleted, oldTargetsNotDeleted, oldTargetsNotFound = "","",""
    # deletedSources, copiedSources, copiedSources, notCopied, copyFailed = "","","","",""

    oldTargetsDeleted, oldTargetsNotDeleted, oldTargetsNotFound = removeOldTargets(baseSourceFile, baseTargetPath,
                                                                                   verbose, silent)
    deletedSources, copiedSources, copiedSources, notCopied, copyFailed = copyNewTargets(baseSourcePath, baseTargetPath,
                                                                                         baseTargetMD5File, verbose,
                                                                                         silent)

    print("----------------------------------------------------------------------------------------------------")
    print("oldTargetsNotFound:\n{}".format(oldTargetsNotFound))
    print("\n\noldTargetsNotDeleted:\n{}".format(oldTargetsNotDeleted))
    print("\n\noldTargetsDeleted:\n{}".format(oldTargetsDeleted))
    print("\n\n-----------")
    print("\n\ncopiedSources:\n{}".format(copiedSources))
    print("\n\ndeletedSources:\n{}".format(deletedSources))
    print("\n\nnotCopied:\n{}".format(notCopied))
    print("\n\ncopyFailed:\n{}".format(copyFailed))
    print("\n----------------------------------------------------------------------------------------------------")


if __name__ == "__main__":
    main(sys.argv)
