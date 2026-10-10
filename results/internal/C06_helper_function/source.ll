; ModuleID = '/home/zhovy/work/Case_Regression_Internal/cases/C06_helper_function/case.c'
source_filename = "/home/zhovy/work/Case_Regression_Internal/cases/C06_helper_function/case.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@shared = dso_local global i32 0, align 4, !dbg !0

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @writer(ptr noundef %0) #0 !dbg !15 {
  %2 = alloca ptr, align 8
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !20, metadata !DIExpression()), !dbg !21
  %3 = load ptr, ptr %2, align 8, !dbg !22
  call void @helper_write(), !dbg !23
  ret ptr null, !dbg !24
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define internal void @helper_write() #0 !dbg !25 {
  store i32 1, ptr @shared, align 4, !dbg !28
  ret void, !dbg !29
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @reader(ptr noundef %0) #0 !dbg !30 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !31, metadata !DIExpression()), !dbg !32
  %4 = load ptr, ptr %2, align 8, !dbg !33
  call void @llvm.dbg.declare(metadata ptr %3, metadata !34, metadata !DIExpression()), !dbg !35
  %5 = call i32 @helper_read(), !dbg !36
  store i32 %5, ptr %3, align 4, !dbg !35
  %6 = load i32, ptr %3, align 4, !dbg !37
  ret ptr null, !dbg !38
}

; Function Attrs: noinline nounwind optnone uwtable
define internal i32 @helper_read() #0 !dbg !39 {
  %1 = load i32, ptr @shared, align 4, !dbg !42
  ret i32 %1, !dbg !43
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !44 {
  %1 = alloca i32, align 4
  %2 = alloca i64, align 8
  %3 = alloca i64, align 8
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !45, metadata !DIExpression()), !dbg !49
  call void @llvm.dbg.declare(metadata ptr %3, metadata !50, metadata !DIExpression()), !dbg !51
  %4 = call i32 @pthread_create(ptr noundef %2, ptr noundef null, ptr noundef @writer, ptr noundef null) #4, !dbg !52
  %5 = call i32 @pthread_create(ptr noundef %3, ptr noundef null, ptr noundef @reader, ptr noundef null) #4, !dbg !53
  %6 = load i64, ptr %2, align 8, !dbg !54
  %7 = call i32 @pthread_join(i64 noundef %6, ptr noundef null), !dbg !55
  %8 = load i64, ptr %3, align 8, !dbg !56
  %9 = call i32 @pthread_join(i64 noundef %8, ptr noundef null), !dbg !57
  ret i32 0, !dbg !58
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
!llvm.module.flags = !{!7, !8, !9, !10, !11, !12, !13}
!llvm.ident = !{!14}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "shared", scope: !2, file: !5, line: 3, type: !6, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C11, file: !3, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, globals: !4, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/home/zhovy/work/Case_Regression_Internal/cases/C06_helper_function/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "33a36636ccd95882225788b387277e60")
!4 = !{!0}
!5 = !DIFile(filename: "cases/C06_helper_function/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "33a36636ccd95882225788b387277e60")
!6 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!7 = !{i32 7, !"Dwarf Version", i32 5}
!8 = !{i32 2, !"Debug Info Version", i32 3}
!9 = !{i32 1, !"wchar_size", i32 4}
!10 = !{i32 8, !"PIC Level", i32 2}
!11 = !{i32 7, !"PIE Level", i32 2}
!12 = !{i32 7, !"uwtable", i32 2}
!13 = !{i32 7, !"frame-pointer", i32 2}
!14 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!15 = distinct !DISubprogram(name: "writer", scope: !5, file: !5, line: 8, type: !16, scopeLine: 8, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !19)
!16 = !DISubroutineType(types: !17)
!17 = !{!18, !18}
!18 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: null, size: 64)
!19 = !{}
!20 = !DILocalVariable(name: "arg", arg: 1, scope: !15, file: !5, line: 8, type: !18)
!21 = !DILocation(line: 8, column: 20, scope: !15)
!22 = !DILocation(line: 9, column: 11, scope: !15)
!23 = !DILocation(line: 10, column: 5, scope: !15)
!24 = !DILocation(line: 11, column: 5, scope: !15)
!25 = distinct !DISubprogram(name: "helper_write", scope: !5, file: !5, line: 5, type: !26, scopeLine: 5, flags: DIFlagPrototyped, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !2)
!26 = !DISubroutineType(types: !27)
!27 = !{null}
!28 = !DILocation(line: 5, column: 41, scope: !25)
!29 = !DILocation(line: 5, column: 46, scope: !25)
!30 = distinct !DISubprogram(name: "reader", scope: !5, file: !5, line: 14, type: !16, scopeLine: 14, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !19)
!31 = !DILocalVariable(name: "arg", arg: 1, scope: !30, file: !5, line: 14, type: !18)
!32 = !DILocation(line: 14, column: 20, scope: !30)
!33 = !DILocation(line: 15, column: 11, scope: !30)
!34 = !DILocalVariable(name: "seen", scope: !30, file: !5, line: 16, type: !6)
!35 = !DILocation(line: 16, column: 9, scope: !30)
!36 = !DILocation(line: 16, column: 16, scope: !30)
!37 = !DILocation(line: 17, column: 11, scope: !30)
!38 = !DILocation(line: 18, column: 5, scope: !30)
!39 = distinct !DISubprogram(name: "helper_read", scope: !5, file: !5, line: 6, type: !40, scopeLine: 6, flags: DIFlagPrototyped, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !2)
!40 = !DISubroutineType(types: !41)
!41 = !{!6}
!42 = !DILocation(line: 6, column: 39, scope: !39)
!43 = !DILocation(line: 6, column: 32, scope: !39)
!44 = distinct !DISubprogram(name: "main", scope: !5, file: !5, line: 21, type: !40, scopeLine: 21, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !19)
!45 = !DILocalVariable(name: "first", scope: !44, file: !5, line: 22, type: !46)
!46 = !DIDerivedType(tag: DW_TAG_typedef, name: "pthread_t", file: !47, line: 27, baseType: !48)
!47 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/pthreadtypes.h", directory: "", checksumkind: CSK_MD5, checksum: "8a5acdbeec491eca11cf81cb1ef77ea7")
!48 = !DIBasicType(name: "unsigned long", size: 64, encoding: DW_ATE_unsigned)
!49 = !DILocation(line: 22, column: 15, scope: !44)
!50 = !DILocalVariable(name: "second", scope: !44, file: !5, line: 22, type: !46)
!51 = !DILocation(line: 22, column: 22, scope: !44)
!52 = !DILocation(line: 23, column: 5, scope: !44)
!53 = !DILocation(line: 24, column: 5, scope: !44)
!54 = !DILocation(line: 25, column: 18, scope: !44)
!55 = !DILocation(line: 25, column: 5, scope: !44)
!56 = !DILocation(line: 26, column: 18, scope: !44)
!57 = !DILocation(line: 26, column: 5, scope: !44)
!58 = !DILocation(line: 27, column: 5, scope: !44)
