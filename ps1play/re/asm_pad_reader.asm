; pad_reader (xref site 0x80015714, func start 0x800156e4)  (start 0x800156e4, 768 bytes)
800156E4: nop      
800156E8: addiu    $sp, $sp, -0x20
800156EC: sw       $s1, 0x14($sp)
800156F0: lui      $s1, 0x800d
800156F4: lbu      $a0, 0x4a72($s1)
800156F8: sw       $ra, 0x18($sp)
800156FC: bnez     $a0, 0x800158cc
80015700: sw       $s0, 0x10($sp)
80015704: lui      $v0, 0x800d
80015708: lbu      $v0, -0x65a6($v0)
8001570C: nop      
80015710: srl      $s1, $v0, 1
80015714: lui      $v0, 0x800d
80015718: addiu    $v0, $v0, 0x4948
8001571C: sll      $v1, $s1, 3
80015720: addu     $s0, $v1, $v0
80015724: lhu      $v0, 2($s0)
80015728: nop      
8001572C: andi     $v0, $v0, 0x50
80015730: beqz     $v0, 0x80015788
80015734: lui      $v0, 0x800d
80015738: jal      0x8001d5a0
8001573C: addiu    $a0, $zero, 0x18
80015740: lhu      $v0, 2($s0)
80015744: nop      
80015748: andi     $v0, $v0, 0x10
8001574C: beqz     $v0, 0x80015760
80015750: lui      $v1, 0x800d
80015754: lbu      $v0, 0x4a71($v1)
80015758: j        0x8001576c
8001575C: addiu    $v0, $v0, -1
80015760: lbu      $v0, 0x4a71($v1)
80015764: nop      
80015768: addiu    $v0, $v0, 1
8001576C: sb       $v0, 0x4a71($v1)
80015770: lui      $v1, 0x800d
80015774: lbu      $v0, 0x4a71($v1)
80015778: nop      
8001577C: andi     $v0, $v0, 3
80015780: sb       $v0, 0x4a71($v1)
80015784: lui      $v0, 0x800d
80015788: lb       $v1, 0x4a71($v0)
8001578C: addiu    $v0, $zero, 2
80015790: bne      $v1, $v0, 0x80015840
80015794: lui      $v0, 0x800d
80015798: addiu    $v0, $v0, 0x4948
8001579C: sll      $v1, $s1, 3
800157A0: addu     $v1, $v1, $v0
800157A4: lui      $a0, 0x800d
800157A8: lhu      $v0, 2($v1)
800157AC: lbu      $a1, 0x4a70($a0)
800157B0: andi     $v0, $v0, 0x80
800157B4: beqz     $v0, 0x800157c0
800157B8: addiu    $v0, $a1, -1
800157BC: sb       $v0, 0x4a70($a0)
800157C0: lhu      $v0, 2($v1)
800157C4: nop      
800157C8: andi     $v0, $v0, 0x20
800157CC: beqz     $v0, 0x800157e4
800157D0: nop      
800157D4: lbu      $v0, 0x4a70($a0)
800157D8: nop      
800157DC: addiu    $v0, $v0, 1
800157E0: sb       $v0, 0x4a70($a0)
800157E4: lb       $v0, 0x4a70($a0)
800157E8: nop      
800157EC: bgez     $v0, 0x80015808
800157F0: lui      $v0, 0x800d
800157F4: lbu      $v0, 0x4210($v0)
800157F8: nop      
800157FC: addiu    $v0, $v0, -1
80015800: sb       $v0, 0x4a70($a0)
80015804: lui      $v0, 0x800d
80015808: lb       $v1, 0x4a70($a0)
8001580C: lh       $v0, 0x4210($v0)
80015810: nop      
80015814: slt      $v1, $v1, $v0
80015818: bnez     $v1, 0x80015824
8001581C: sll      $v0, $a1, 0x18
80015820: sb       $zero, 0x4a70($a0)
80015824: lb       $v1, 0x4a70($a0)
80015828: sra      $v0, $v0, 0x18
8001582C: beq      $v0, $v1, 0x80015840
80015830: lui      $v0, 0x800d
80015834: jal      0x8001d5a0
80015838: addiu    $a0, $zero, 0x18
8001583C: lui      $v0, 0x800d
80015840: addiu    $v0, $v0, 0x4948
80015844: sll      $v1, $s1, 3
80015848: addu     $v1, $v1, $v0
8001584C: lhu      $v0, 2($v1)
80015850: nop      
80015854: andi     $v0, $v0, 0x4000
80015858: beqz     $v0, 0x800159b4
8001585C: lui      $v0, 0x800d
80015860: lb       $v0, 0x4a71($v0)
80015864: nop      
80015868: bnez     $v0, 0x80015888
8001586C: addiu    $a0, $zero, 0x10
80015870: lui      $v0, 0x800d
80015874: lui      $v1, 0x800d
80015878: sb       $zero, -0x65a4($v0)
8001587C: addiu    $v0, $zero, 4
80015880: j        0x800159bc
80015884: sb       $v0, -0x6592($v1)
80015888: lui      $v0, 0x800d
8001588C: lui      $v1, 0x800d
80015890: sb       $zero, -0x65a5($v0)
80015894: addiu    $v0, $zero, 0x20
80015898: sb       $v0, -0x65a4($v1)
8001589C: lui      $v0, 0x800d
800158A0: lui      $v1, 0x800d
800158A4: sb       $zero, -0x659c($v0)
800158A8: addiu    $v0, $zero, 1
800158AC: jal      0x80016d9c
800158B0: sb       $v0, 0x4a72($v1)
800158B4: jal      0x80016fcc
800158B8: nop      
800158BC: lui      $v1, 0x800d
800158C0: addiu    $v0, $zero, 0x10
800158C4: j        0x800159b4
800158C8: sh       $v0, 0x4a6e($v1)
800158CC: addiu    $v1, $zero, 1
800158D0: bne      $a0, $v1, 0x80015930
800158D4: addiu    $v0, $zero, 2
800158D8: lui      $s0, 0x800d
800158DC: lhu      $v0, 0x4a6e($s0)
800158E0: nop      
800158E4: addiu    $v0, $v0, -1
800158E8: sh       $v0, 0x4a6e($s0)
800158EC: sll      $v0, $v0, 0x10
800158F0: bgtz     $v0, 0x80015914
800158F4: nop      
800158F8: jal      0x8001ce18
800158FC: nop      
80015900: addiu    $a0, $zero, -1
80015904: jal      0x80016f38
80015908: move     $a1, $zero
8001590C: addiu    $v0, $zero, 2
80015910: sb       $v0, 0x4a72($s1)
80015914: lh       $a0, 0x4a6e($s0)
80015918: nop      
8001591C: sll      $a0, $a0, 3
80015920: jal      0x8002b28c
80015924: addiu    $a0, $a0, -1
80015928: j        0x800159b4
8001592C: nop      
80015930: bne      $a0, $v0, 0x800159b4
80015934: lui      $v0, 0x800f
80015938: lh       $v0, -0x4a8c($v0)
8001593C: nop      
80015940: bnez     $v0, 0x800159bc
80015944: lui      $v0, 0x800d
80015948: sb       $zero, -0x65a4($v0)
8001594C: lui      $v0, 0x800d
80015950: lb       $a1, 0x4a71($v0)
80015954: lui      $a2, 0x800d
80015958: bne      $a1, $v1, 0x8001596c
8001595C: sw       $zero, 0x496c($a2)
80015960: lui      $v1, 0x800f
80015964: addiu    $v0, $zero, 0xff
80015968: sb       $v0, -0x24ae($v1)
8001596C: bne      $a1, $a0, 0x8001599c
80015970: addiu    $v0, $zero, 3
80015974: lui      $v0, 0x800d
80015978: lui      $a0, 0x800f
8001597C: lbu      $v0, 0x4a70($v0)
80015980: addiu    $v1, $zero, 0xff
80015984: sb       $v1, -0x24ae($a0)
80015988: lui      $v1, 0x800f
8001598C: sll      $v0, $v0, 0x18
80015990: sra      $v0, $v0, 0x18
80015994: sh       $v0, -0x24d0($v1)
80015998: addiu    $v0, $zero, 3
8001599C: bne      $a1, $v0, 0x800159b4
800159A0: lui      $v0, 0x800f
800159A4: addiu    $v1, $zero, 0xff
800159A8: sb       $v1, -0x2498($v0)
800159AC: addiu    $v0, $zero, -1
800159B0: sw       $v0, 0x496c($a2)
800159B4: jal      0x8001560c
800159B8: nop      
800159BC: lw       $ra, 0x18($sp)
800159C0: lw       $s1, 0x14($sp)
800159C4: lw       $s0, 0x10($sp)
800159C8: jr       $ra
800159CC: addiu    $sp, $sp, 0x20
800159D0: addiu    $sp, $sp, -0x30
800159D4: lui      $a0, 0x8001
800159D8: addiu    $a0, $a0, 0x7c
800159DC: addiu    $a1, $zero, 0xa0
800159E0: addiu    $a2, $zero, 1