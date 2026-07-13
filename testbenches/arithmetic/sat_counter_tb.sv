// testbenches/arithmetic/sat_counter_tb.sv
`timescale 1ns/1ps
module tb;
    localparam WIDTH = 4;
    localparam MAX_VAL = (1 << WIDTH) - 1;

    logic clk = 0, rst_n = 0, up = 0, down = 0;
    logic [WIDTH-1:0] count;
    integer errors = 0;
    integer i;

    sat_counter #(.WIDTH(WIDTH)) dut (.clk(clk), .rst_n(rst_n), .up(up), .down(down), .count(count));

    always #5 clk = ~clk;

    task pulse_up();
        begin @(negedge clk); up = 1; down = 0; @(negedge clk); up = 0; end
    endtask
    task pulse_down();
        begin @(negedge clk); down = 1; up = 0; @(negedge clk); down = 0; end
    endtask
    task check(input [WIDTH-1:0] expected, input string label);
        begin
            #1;
            if (count !== expected) begin
                $display("MISMATCH [%s]: got=%0d expected=%0d", label, count, expected);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        rst_n = 0;
        repeat (2) @(posedge clk);
        rst_n = 1;
        @(posedge clk); #1;
        check(0, "reset value");

        // Try to decrement below 0 -- must saturate at 0
        pulse_down();
        check(0, "floor saturation");

        // Ramp all the way up past MAX_VAL -- must saturate at MAX_VAL
        for (i = 0; i < MAX_VAL + 5; i = i + 1) begin
            pulse_up();
        end
        check(MAX_VAL, "ceiling saturation");

        // Attempt one more increment while at ceiling -- must hold
        pulse_up();
        check(MAX_VAL, "hold at ceiling");

        // Now decrement back down fully and check it stops at 0, not wraps
        for (i = 0; i < MAX_VAL + 5; i = i + 1) begin
            pulse_down();
        end
        check(0, "floor after full drain");

        if (errors == 0)
            $display("SIM_PASS");
        else
            $display("SIM_FAIL: %0d mismatches", errors);
        $finish;
    end

    initial begin
        #100000;
        $display("SIM_FAIL: timeout");
        $finish;
    end
endmodule
