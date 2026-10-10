; ModuleID = '/home/zhovy/work/Case_Regression_Internal/cases/C08_unrelated_code/case.c'
source_filename = "/home/zhovy/work/Case_Regression_Internal/cases/C08_unrelated_code/case.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@data = dso_local global i32 0, align 4, !dbg !0
@flag = dso_local global i32 0, align 4, !dbg !5
@noise = dso_local global i32 0, align 4, !dbg !9

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @writer(ptr noundef %0) #0 !dbg !19 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !24, metadata !DIExpression()), !dbg !25
  %4 = load ptr, ptr %2, align 8, !dbg !26
  call void @llvm.dbg.declare(metadata ptr %3, metadata !27, metadata !DIExpression()), !dbg !28
  %5 = call i32 @unrelated(i32 noundef 3), !dbg !29
  store i32 %5, ptr %3, align 4, !dbg !28
  %6 = load i32, ptr %3, align 4, !dbg !30
  store i32 7, ptr @noise, align 4, !dbg !31
  store i32 1, ptr @data, align 4, !dbg !32
  store i32 1, ptr @flag, align 4, !dbg !33
  ret ptr null, !dbg !34
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define internal i32 @unrelated(i32 noundef %0) #0 !dbg !35 {
  %2 = alloca i32, align 4
  store i32 %0, ptr %2, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !38, metadata !DIExpression()), !dbg !39
  %3 = load i32, ptr %2, align 4, !dbg !40
  %4 = mul nsw i32 %3, 2, !dbg !41
  ret i32 %4, !dbg !42
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @reader(ptr noundef %0) #0 !dbg !43 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !44, metadata !DIExpression()), !dbg !45
  %5 = load ptr, ptr %2, align 8, !dbg !46
  call void @llvm.dbg.declare(metadata ptr %3, metadata !47, metadata !DIExpression()), !dbg !48
  %6 = load i32, ptr @flag, align 4, !dbg !49
  store i32 %6, ptr %3, align 4, !dbg !48
  call void @llvm.dbg.declare(metadata ptr %4, metadata !50, metadata !DIExpression()), !dbg !51
  %7 = load i32, ptr @data, align 4, !dbg !52
  store i32 %7, ptr %4, align 4, !dbg !51
  %8 = load i32, ptr %3, align 4, !dbg !53
  %9 = load i32, ptr %4, align 4, !dbg !54
  ret ptr null, !dbg !55
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !56 {
  %1 = alloca i32, align 4
  %2 = alloca i64, align 8
  %3 = alloca i64, align 8
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !59, metadata !DIExpression()), !dbg !63
  call void @llvm.dbg.declare(metadata ptr %3, metadata !64, metadata !DIExpression()), !dbg !65
  %4 = call i32 @pthread_create(ptr noundef %2, ptr noundef null, ptr noundef @writer, ptr noundef null) #4, !dbg !66
  %5 = call i32 @pthread_create(ptr noundef %3, ptr noundef null, ptr noundef @reader, ptr noundef null) #4, !dbg !67
  %6 = load i64, ptr %2, align 8, !dbg !68
  %7 = call i32 @pthread_join(i64 noundef %6, ptr noundef null), !dbg !69
  %8 = load i64, ptr %3, align 8, !dbg !70
  %9 = call i32 @pthread_join(i64 noundef %8, ptr noundef null), !dbg !71
  ret i32 0, !dbg !72
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
!1 = distinct !DIGlobalVariable(name: "data", scope: !2, file: !7, line: 3, type: !8, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C11, file: !3, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, globals: !4, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/home/zhovy/work/Case_Regression_Internal/cases/C08_unrelated_code/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "b31e6def811b300aed802a22e8d80a44")
!4 = !{!0, !5, !9}
!5 = !DIGlobalVariableExpression(var: !6, expr: !DIExpression())
!6 = distinct !DIGlobalVariable(name: "flag", scope: !2, file: !7, line: 4, type: !8, isLocal: false, isDefinition: true)
!7 = !DIFile(filename: "cases/C08_unrelated_code/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "b31e6def811b300aed802a22e8d80a44")
!8 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!9 = !DIGlobalVariableExpression(var: !10, expr: !DIExpression())
!10 = distinct !DIGlobalVariable(name: "noise", scope: !2, file: !7, line: 5, type: !8, isLocal: false, isDefinition: true)
!11 = !{i32 7, !"Dwarf Version", i32 5}
!12 = !{i32 2, !"Debug Info Version", i32 3}
!13 = !{i32 1, !"wchar_size", i32 4}
!14 = !{i32 8, !"PIC Level", i32 2}
!15 = !{i32 7, !"PIE Level", i32 2}
!16 = !{i32 7, !"uwtable", i32 2}
!17 = !{i32 7, !"frame-pointer", i32 2}
!18 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!19 = distinct !DISubprogram(name: "writer", scope: !7, file: !7, line: 9, type: !20, scopeLine: 9, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!20 = !DISubroutineType(types: !21)
!21 = !{!22, !22}
!22 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: null, size: 64)
!23 = !{}
!24 = !DILocalVariable(name: "arg", arg: 1, scope: !19, file: !7, line: 9, type: !22)
!25 = !DILocation(line: 9, column: 20, scope: !19)
!26 = !DILocation(line: 10, column: 11, scope: !19)
!27 = !DILocalVariable(name: "local", scope: !19, file: !7, line: 11, type: !8)
!28 = !DILocation(line: 11, column: 9, scope: !19)
!29 = !DILocation(line: 11, column: 17, scope: !19)
!30 = !DILocation(line: 12, column: 11, scope: !19)
!31 = !DILocation(line: 13, column: 11, scope: !19)
!32 = !DILocation(line: 14, column: 10, scope: !19)
!33 = !DILocation(line: 15, column: 10, scope: !19)
!34 = !DILocation(line: 16, column: 5, scope: !19)
!35 = distinct !DISubprogram(name: "unrelated", scope: !7, file: !7, line: 7, type: !36, scopeLine: 7, flags: DIFlagPrototyped, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !2, retainedNodes: !23)
!36 = !DISubroutineType(types: !37)
!37 = !{!8, !8}
!38 = !DILocalVariable(name: "value", arg: 1, scope: !35, file: !7, line: 7, type: !8)
!39 = !DILocation(line: 7, column: 26, scope: !35)
!40 = !DILocation(line: 7, column: 42, scope: !35)
!41 = !DILocation(line: 7, column: 48, scope: !35)
!42 = !DILocation(line: 7, column: 35, scope: !35)
!43 = distinct !DISubprogram(name: "reader", scope: !7, file: !7, line: 19, type: !20, scopeLine: 19, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!44 = !DILocalVariable(name: "arg", arg: 1, scope: !43, file: !7, line: 19, type: !22)
!45 = !DILocation(line: 19, column: 20, scope: !43)
!46 = !DILocation(line: 20, column: 11, scope: !43)
!47 = !DILocalVariable(name: "seen_flag", scope: !43, file: !7, line: 21, type: !8)
!48 = !DILocation(line: 21, column: 9, scope: !43)
!49 = !DILocation(line: 21, column: 21, scope: !43)
!50 = !DILocalVariable(name: "seen_data", scope: !43, file: !7, line: 22, type: !8)
!51 = !DILocation(line: 22, column: 9, scope: !43)
!52 = !DILocation(line: 22, column: 21, scope: !43)
!53 = !DILocation(line: 23, column: 11, scope: !43)
!54 = !DILocation(line: 24, column: 11, scope: !43)
!55 = !DILocation(line: 25, column: 5, scope: !43)
!56 = distinct !DISubprogram(name: "main", scope: !7, file: !7, line: 28, type: !57, scopeLine: 28, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!57 = !DISubroutineType(types: !58)
!58 = !{!8}
!59 = !DILocalVariable(name: "first", scope: !56, file: !7, line: 29, type: !60)
!60 = !DIDerivedType(tag: DW_TAG_typedef, name: "pthread_t", file: !61, line: 27, baseType: !62)
!61 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/pthreadtypes.h", directory: "", checksumkind: CSK_MD5, checksum: "8a5acdbeec491eca11cf81cb1ef77ea7")
!62 = !DIBasicType(name: "unsigned long", size: 64, encoding: DW_ATE_unsigned)
!63 = !DILocation(line: 29, column: 15, scope: !56)
!64 = !DILocalVariable(name: "second", scope: !56, file: !7, line: 29, type: !60)
!65 = !DILocation(line: 29, column: 22, scope: !56)
!66 = !DILocation(line: 30, column: 5, scope: !56)
!67 = !DILocation(line: 31, column: 5, scope: !56)
!68 = !DILocation(line: 32, column: 18, scope: !56)
!69 = !DILocation(line: 32, column: 5, scope: !56)
!70 = !DILocation(line: 33, column: 18, scope: !56)
!71 = !DILocation(line: 33, column: 5, scope: !56)
!72 = !DILocation(line: 34, column: 5, scope: !56)
