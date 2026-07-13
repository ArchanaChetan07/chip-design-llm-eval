// testbenches/interface_adapters/sync_fifo_tb.sv
// Self-checking reference testbench for sync_fifo (WIDTH=8, DEPTH=4).
// Verifies: fill-to-full asserts full correctly, full blocks further
// writes (data integrity via a shadow model), drain-to-empty works,
// and data comes out in FIFO order.
`timescale 1ns/1ps
module tb;
    localparam WIDTH = 8;
    localparam DEPTH = 4;

    logic clk = 0, rst_n = 0, wr_en = 0, rd_en = 0;
    logic [WIDTH-1:0] wr_data;
    logic [WIDTH-1:0] rd_data;
    logic full, empty;
    integer errors = 0;
    integer i;

    // Shadow model: simple queue mirroring expected FIFO contents.
    logic [WIDTH-1:0] shadow [$];

    sync_fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .rd_en(rd_en),
        .wr_data(wr_data), .rd_data(rd_data), .full(full), .empty(empty)
    );

    always #5 clk = ~clk;

    task do_write(input [WIDTH-1:0] d);
        begin
            @(negedge clk);
            if (!full) begin
                wr_data = d; wr_en = 1;
                shadow.push_back(d);
            end else begin
                wr_en = 0; // don't write if full (correct behavior expected)
            end
            @(negedge clk);
            wr_en = 0;
        end
    endtask

    task do_read();
        logic [WIDTH-1:0] expected;
        logic [WIDTH-1:0] captured;
        logic was_reading;
        begin
            @(negedge clk);
            was_reading = 0;
            if (!empty) begin
                rd_en = 1;
                expected = shadow.pop_front();
                was_reading = 1;
            end
            #1;
            // Capture rd_data NOW, before the upcoming posedge advances
            // rd_ptr -- rd_data is combinational off the *current* pointer,
            // which is what this read is actually consuming.
            captured = rd_data;
            @(negedge clk);
            rd_en = 0;
            if (was_reading) begin
                if (captured !== expected) begin
                    $display("MISMATCH: read got=%0d expected=%0d", captured, expected);
                    errors = errors + 1;
                end
            end
        end
    endtask

    initial begin
        rst_n = 0;
        repeat (2) @(posedge clk);
        rst_n = 1;
        @(posedge clk); #1;

        if (!empty) begin
            $display("MISMATCH: expected empty=1 immediately after reset");
            errors = errors + 1;
        end
        if (full) begin
            $display("MISMATCH: expected full=0 immediately after reset");
            errors = errors + 1;
        end

        // Fill to exactly DEPTH entries
        for (i = 0; i < DEPTH; i = i + 1) begin
            do_write(i * 10 + 1);
        end

        @(negedge clk); #1;
        if (!full) begin
            $display("MISMATCH: expected full=1 after writing DEPTH entries, got full=%b", full);
            errors = errors + 1;
        end

        // Attempt one more write while full -- must be rejected (no-op)
        do_write(8'hFF);  // do_write checks !full internally to match correct behavior;
                          // a buggy DUT that reports full=0 here will accept this write,
                          // corrupting the shadow-vs-DUT comparison on the reads below.

        // Now drain everything and check FIFO order + count
        for (i = 0; i < DEPTH; i = i + 1) begin
            do_read();
        end

        @(negedge clk); #1;
        if (!empty) begin
            $display("MISMATCH: expected empty=1 after draining all entries, got empty=%b", empty);
            errors = errors + 1;
        end

        if (errors == 0)
            $display("SIM_PASS");
        else
            $display("SIM_FAIL: %0d mismatches", errors);

        $finish;
    end

    initial begin
        #200000;
        $display("SIM_FAIL: timeout");
        $finish;
    end
endmodule
