; ModuleID = '/home/zhovy/work/Case_Regression_Internal/cases/P01_pthread_sb/case.c'
source_filename = "/home/zhovy/work/Case_Regression_Internal/cases/P01_pthread_sb/case.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@x = dso_local global i32 0, align 4, !dbg !0
@y = dso_local global i32 0, align 4, !dbg !5
@private_noise = dso_local global i32 0, align 4, !dbg !9

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @writer(ptr noundef %0) #0 !dbg !19 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !24, metadata !DIExpression()), !dbg !25
  %4 = load ptr, ptr %2, align 8, !dbg !26
  store i32 1, ptr @x, align 4, !dbg !27
  call void @llvm.dbg.declare(metadata ptr %3, metadata !28, metadata !DIExpression()), !dbg !29
  %5 = load i32, ptr @y, align 4, !dbg !30
  store i32 %5, ptr %3, align 4, !dbg !29
  store i32 7, ptr @private_noise, align 4, !dbg !31
  %6 = load i32, ptr %3, align 4, !dbg !32
  ret ptr null, !dbg !33
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @reader(ptr noundef %0) #0 !dbg !34 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !35, metadata !DIExpression()), !dbg !36
  %4 = load ptr, ptr %2, align 8, !dbg !37
  store i32 1, ptr @y, align 4, !dbg !38
  call void @llvm.dbg.declare(metadata ptr %3, metadata !39, metadata !DIExpression()), !dbg !40
  %5 = load i32, ptr @x, align 4, !dbg !41
  store i32 %5, ptr %3, align 4, !dbg !40
  %6 = load i32, ptr %3, align 4, !dbg !42
  ret ptr null, !dbg !43
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !44 {
  %1 = alloca i32, align 4
  %2 = alloca i64, align 8
  %3 = alloca i64, align 8
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !47, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.declare(metadata ptr %3, metadata !52, metadata !DIExpression()), !dbg !53
  %4 = call i32 @pthread_create(ptr noundef %2, ptr noundef null, ptr noundef @writer, ptr noundef null) #4, !dbg !54
  %5 = call i32 @pthread_create(ptr noundef %3, ptr noundef null, ptr noundef @reader, ptr noundef null) #4, !dbg !55
  %6 = load i64, ptr %2, align 8, !dbg !56
  %7 = call i32 @pthread_join(i64 noundef %6, ptr noundef null), !dbg !57
  %8 = load i64, ptr %3, align 8, !dbg !58
  %9 = call i32 @pthread_join(i64 noundef %8, ptr noundef null), !dbg !59
  ret i32 0, !dbg !60
}

; Function Attrs: nounwind
declare i32 @pthread_create(ptr noundef, ptr noundef, ptr noundef, ptr noundef) #2

declare i32 @pthread_join(i64 noundef, ptr noundef) #3

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { nounwind "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { nounwind }

!llvm.dbg.cu = !{!2}
!llvm.module.flags = !{!11, !12, !13, !14, !15, !16, !17}
!llvm.ident = !{!18}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "x", scope: !2, file: !7, line: 4, type: !8, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C11, file: !3, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, globals: !4, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/home/zhovy/work/Case_Regression_Internal/cases/P01_pthread_sb/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "0578946b4231c8d6848d1beaeeca62b3")
!4 = !{!0, !5, !9}
!5 = !DIGlobalVariableExpression(var: !6, expr: !DIExpression())
!6 = distinct !DIGlobalVariable(name: "y", scope: !2, file: !7, line: 5, type: !8, isLocal: false, isDefinition: true)
!7 = !DIFile(filename: "cases/P01_pthread_sb/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "0578946b4231c8d6848d1beaeeca62b3")
!8 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!9 = !DIGlobalVariableExpression(var: !10, expr: !DIExpression())
!10 = distinct !DIGlobalVariable(name: "private_noise", scope: !2, file: !7, line: 6, type: !8, isLocal: false, isDefinition: true)
!11 = !{i32 7, !"Dwarf Version", i32 5}
!12 = !{i32 2, !"Debug Info Version", i32 3}
!13 = !{i32 1, !"wchar_size", i32 4}
!14 = !{i32 8, !"PIC Level", i32 2}
!15 = !{i32 7, !"PIE Level", i32 2}
!16 = !{i32 7, !"uwtable", i32 2}
!17 = !{i32 7, !"frame-pointer", i32 2}
!18 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!19 = distinct !DISubprogram(name: "writer", scope: !7, file: !7, line: 8, type: !20, scopeLine: 8, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!20 = !DISubroutineType(types: !21)
!21 = !{!22, !22}
!22 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: null, size: 64)
!23 = !{}
!24 = !DILocalVariable(name: "arg", arg: 1, scope: !19, file: !7, line: 8, type: !22)
!25 = !DILocation(line: 8, column: 20, scope: !19)
!26 = !DILocation(line: 9, column: 11, scope: !19)
!27 = !DILocation(line: 10, column: 7, scope: !19)
!28 = !DILocalVariable(name: "r0", scope: !19, file: !7, line: 11, type: !8)
!29 = !DILocation(line: 11, column: 9, scope: !19)
!30 = !DILocation(line: 11, column: 14, scope: !19)
!31 = !DILocation(line: 12, column: 19, scope: !19)
!32 = !DILocation(line: 13, column: 11, scope: !19)
!33 = !DILocation(line: 14, column: 5, scope: !19)
!34 = distinct !DISubprogram(name: "reader", scope: !7, file: !7, line: 17, type: !20, scopeLine: 17, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!35 = !DILocalVariable(name: "arg", arg: 1, scope: !34, file: !7, line: 17, type: !22)
!36 = !DILocation(line: 17, column: 20, scope: !34)
!37 = !DILocation(line: 18, column: 11, scope: !34)
!38 = !DILocation(line: 19, column: 7, scope: !34)
!39 = !DILocalVariable(name: "r1", scope: !34, file: !7, line: 20, type: !8)
!40 = !DILocation(line: 20, column: 9, scope: !34)
!41 = !DILocation(line: 20, column: 14, scope: !34)
!42 = !DILocation(line: 21, column: 11, scope: !34)
!43 = !DILocation(line: 22, column: 5, scope: !34)
!44 = distinct !DISubprogram(name: "main", scope: !7, file: !7, line: 25, type: !45, scopeLine: 25, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!45 = !DISubroutineType(types: !46)
!46 = !{!8}
!47 = !DILocalVariable(name: "first", scope: !44, file: !7, line: 26, type: !48)
!48 = !DIDerivedType(tag: DW_TAG_typedef, name: "pthread_t", file: !49, line: 27, baseType: !50)
!49 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/pthreadtypes.h", directory: "", checksumkind: CSK_MD5, checksum: "8a5acdbeec491eca11cf81cb1ef77ea7")
!50 = !DIBasicType(name: "unsigned long", size: 64, encoding: DW_ATE_unsigned)
!51 = !DILocation(line: 26, column: 15, scope: !44)
!52 = !DILocalVariable(name: "second", scope: !44, file: !7, line: 26, type: !48)
!53 = !DILocation(line: 26, column: 22, scope: !44)
!54 = !DILocation(line: 27, column: 5, scope: !44)
!55 = !DILocation(line: 28, column: 5, scope: !44)
!56 = !DILocation(line: 29, column: 18, scope: !44)
!57 = !DILocation(line: 29, column: 5, scope: !44)
!58 = !DILocation(line: 30, column: 18, scope: !44)
!59 = !DILocation(line: 30, column: 5, scope: !44)
!60 = !DILocation(line: 31, column: 5, scope: !44)
