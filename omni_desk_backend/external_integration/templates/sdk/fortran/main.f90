/* main.f90 - Fortran 插件示例 */
program plugin_main
    implicit none
    integer :: iostat
    character(len=4096) :: input_line
    character(len=4096) :: output_json

    ! 读取 stdin 整行 JSON 输入
    read(*, '(A)', iostat=iostat) input_line
    if (iostat /= 0) then
        write(0, '(A)') 'Failed to read input'
        stop 1
    end if

    ! TODO: 解析 input_line JSON 并实现业务逻辑

    ! 输出结果 JSON 到 stdout
    output_json = '{"status":"success","result":{}}'
    write(*, '(A)') output_json

end program plugin_main
